from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, BackgroundTasks, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional, List
from dataclasses import asdict
import os
import uuid
import json
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.core.config import settings
from app.models.user import User
from app.models.contract import Contract, ContractType, ContractStatus, ContractVersion, ContractFile
from app.models.review import ReviewTask, ReviewTaskStatus, ReviewOpinion
from app.schemas.contract import (
    ContractCreate,
    ContractUpdate,
    ContractResponse,
    ContractList,
    ContractVersionResponse,
    ContractFileResponse,
    ContractUploadResponse,
)
from app.services.ai_review import review_contract_with_ai, extract_file_content

router = APIRouter()


def generate_contract_no() -> str:
    """Generate contract number"""
    now = datetime.now()
    return f"HT-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


@router.get("", response_model=ContractList)
async def list_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    contract_type: Optional[ContractType] = None,
    status: Optional[ContractStatus] = None,
    department: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取合同列表"""
    query = select(Contract)
    count_query = select(func.count()).select_from(Contract)
    
    if keyword:
        query = query.where(
            (Contract.title.contains(keyword)) |
            (Contract.contract_no.contains(keyword)) |
            (Contract.party_a.contains(keyword)) |
            (Contract.party_b.contains(keyword))
        )
        count_query = count_query.where(
            (Contract.title.contains(keyword)) |
            (Contract.contract_no.contains(keyword)) |
            (Contract.party_a.contains(keyword)) |
            (Contract.party_b.contains(keyword))
        )
    
    if contract_type:
        query = query.where(Contract.contract_type == contract_type)
        count_query = count_query.where(Contract.contract_type == contract_type)
    
    if status:
        query = query.where(Contract.status == status)
        count_query = count_query.where(Contract.status == status)
    
    if department:
        query = query.where(Contract.department == department)
        count_query = count_query.where(Contract.department == department)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    query = query.order_by(Contract.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    contracts = result.scalars().all()
    
    return ContractList(total=total, items=contracts)


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    title: str = Form(...),
    contract_type: Optional[str] = Form("other"),
    party_a: Optional[str] = Form(None),
    party_b: Optional[str] = Form(None),
    amount: Optional[float] = Form(None),
    currency: Optional[str] = Form("CNY"),
    sign_date: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    project_name: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建合同（支持同时上传文件）"""
    # 处理文件上传
    file_path = None
    file_name = None
    file_size = None
    file_type = None
    extracted_info = None
    
    if file:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式，支持: {', '.join(settings.ALLOWED_EXTENSIONS)}",
            )
        
        content = await file.read()
        if len(content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件大小超过限制（最大{settings.MAX_FILE_SIZE // 1024 // 1024}MB）",
            )
        
        upload_dir = os.path.join(settings.UPLOAD_DIR, "contracts")
        os.makedirs(upload_dir, exist_ok=True)
        
        saved_name = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(upload_dir, saved_name)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        file_name = file.filename
        file_size = len(content)
        file_type = file_ext
        
        # AI自动提取合同基本信息
        from app.services.ai_review import extract_contract_info
        extracted_info = await extract_contract_info(file_path)
    
    # 处理合同类型
    try:
        contract_type_enum = ContractType(contract_type) if contract_type else ContractType.OTHER
    except ValueError:
        contract_type_enum = ContractType.OTHER
    
    contract = Contract(
        contract_no=generate_contract_no(),
        title=title or (extracted_info.get("title") if extracted_info else title),
        contract_type=contract_type_enum or (ContractType(extracted_info.get("contract_type")) if extracted_info and extracted_info.get("contract_type") else ContractType.OTHER),
        party_a=party_a or (extracted_info.get("party_a") if extracted_info else None),
        party_b=party_b or (extracted_info.get("party_b") if extracted_info else None),
        amount=amount or (extracted_info.get("amount") if extracted_info else None),
        currency=currency or (extracted_info.get("currency") if extracted_info else "CNY"),
        sign_date=datetime.strptime(sign_date, "%Y-%m-%d") if sign_date else (datetime.strptime(extracted_info["sign_date"], "%Y-%m-%d") if extracted_info and extracted_info.get("sign_date") else None),
        effective_date=datetime.strptime(effective_date, "%Y-%m-%d") if effective_date else (datetime.strptime(extracted_info["effective_date"], "%Y-%m-%d") if extracted_info and extracted_info.get("effective_date") else None),
        expiry_date=datetime.strptime(expiry_date, "%Y-%m-%d") if expiry_date else (datetime.strptime(extracted_info["expiry_date"], "%Y-%m-%d") if extracted_info and extracted_info.get("expiry_date") else None),
        description=description or (extracted_info.get("description") if extracted_info else None),
        department=department,
        project_name=project_name,
        file_path=file_path,
        file_name=file_name,
        file_size=file_size,
        file_type=file_type,
        uploader_id=current_user.id,
        status=ContractStatus.DRAFT,
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    
    # 如果上传了文件，自动保存文件记录
    if file_path and file_name:
        contract_file = ContractFile(
            contract_id=contract.id,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            uploaded_by=current_user.id,
        )
        db.add(contract_file)
        await db.commit()
    
    return contract


@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    contract_type: Optional[ContractType] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传合同文件，自动识别基本信息"""
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式，支持: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )
    
    # Validate file size
    file_content = await file.read()
    if len(file_content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制（最大{settings.MAX_FILE_SIZE // 1024 // 1024}MB）",
        )
    
    # Save file
    upload_dir = os.path.join(settings.UPLOAD_DIR, "contracts")
    os.makedirs(upload_dir, exist_ok=True)
    
    saved_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(upload_dir, saved_name)
    
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # AI自动提取合同基本信息
    from app.services.file_parser import extract_text_from_file
    from app.services.ai_review import extract_contract_info
    
    extracted_info = await extract_contract_info(file_path)
    
    # 使用提取的信息或传入的参数
    contract_title = title or (extracted_info.get("title") if extracted_info else None) or file.filename
    contract_type_val = contract_type or (extracted_info.get("contract_type") if extracted_info else "other")
    
    # Create contract
    contract = Contract(
        contract_no=generate_contract_no(),
        title=contract_title,
        contract_type=ContractType(contract_type_val) if contract_type_val else ContractType.OTHER,
        party_a=extracted_info.get("party_a") if extracted_info else None,
        party_b=extracted_info.get("party_b") if extracted_info else None,
        amount=extracted_info.get("amount") if extracted_info else None,
        currency=extracted_info.get("currency") if extracted_info else "CNY",
        sign_date=datetime.strptime(extracted_info["sign_date"], "%Y-%m-%d") if extracted_info and extracted_info.get("sign_date") else None,
        effective_date=datetime.strptime(extracted_info["effective_date"], "%Y-%m-%d") if extracted_info and extracted_info.get("effective_date") else None,
        expiry_date=datetime.strptime(extracted_info["expiry_date"], "%Y-%m-%d") if extracted_info and extracted_info.get("expiry_date") else None,
        description=extracted_info.get("description") if extracted_info else None,
        file_path=file_path,
        file_name=file.filename,
        file_size=len(file_content),
        file_type=file_ext,
        uploader_id=current_user.id,
        status=ContractStatus.DRAFT,
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    
    return ContractUploadResponse(
        id=contract.id,
        file_name=file.filename,
        file_path=file_path,
        status="success",
        message="合同上传成功，已自动识别基本信息",
    )


@router.post("/extract-info")
async def extract_contract_info_from_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传文件并提取合同基本信息（不创建合同）"""
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式，支持: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )
    
    # Validate file size
    file_content = await file.read()
    if len(file_content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制（最大{settings.MAX_FILE_SIZE // 1024 // 1024}MB）",
        )
    
    # 临时保存文件用于提取
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        from app.services.ai_review import extract_contract_info
        extracted_info = await extract_contract_info(tmp_path)
        return extracted_info or {}
    finally:
        os.unlink(tmp_path)


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取合同详情"""
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    return contract


@router.put("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: int,
    contract_data: ContractUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新合同"""
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    # Update fields
    update_data = contract_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contract, field, value)
    
    await db.commit()
    await db.refresh(contract)
    
    return contract


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除合同"""
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    # Delete file if exists
    if contract.file_path and os.path.exists(contract.file_path):
        os.remove(contract.file_path)
    
    await db.delete(contract)
    await db.commit()


@router.post("/{contract_id}/submit", response_model=ContractResponse)
async def submit_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交合同审查"""
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    if contract.status != ContractStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能提交草稿状态的合同",
        )
    
    contract.status = ContractStatus.PENDING_REVIEW
    await db.commit()
    await db.refresh(contract)
    
    return contract


@router.get("/{contract_id}/versions", response_model=list[ContractVersionResponse])
async def list_contract_versions(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取合同版本列表"""
    result = await db.execute(
        select(ContractVersion)
        .where(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_no.desc())
    )
    versions = result.scalars().all()
    return versions


@router.get("/{contract_id}/files", response_model=list[ContractFileResponse])
async def list_contract_files(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取合同附件列表"""
    result = await db.execute(
        select(ContractFile)
        .where(ContractFile.contract_id == contract_id)
        .order_by(ContractFile.created_at.desc())
    )
    files = result.scalars().all()
    return files


@router.post("/{contract_id}/ai-review")
async def ai_review_contract(
    contract_id: int,
    current_user: User = Depends(require_role("admin", "superadmin", "legal_manager", "legal_specialist")),
    db: AsyncSession = Depends(get_db),
):
    """AI智能审查合同"""
    # 获取合同
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    # 提取文件内容（如有）
    file_content = None
    if contract.file_path:
        file_content = await extract_file_content(contract.file_path)
    
    # 构造合同数据
    contract_data = {
        "title": contract.title,
        "contract_type": contract.contract_type.value if contract.contract_type else "",
        "party_a": contract.party_a,
        "party_b": contract.party_b,
        "amount": str(contract.amount) if contract.amount else None,
        "currency": contract.currency,
        "sign_date": contract.sign_date.strftime("%Y-%m-%d") if contract.sign_date else None,
        "effective_date": contract.effective_date.strftime("%Y-%m-%d") if contract.effective_date else None,
        "expiry_date": contract.expiry_date.strftime("%Y-%m-%d") if contract.expiry_date else None,
        "description": contract.description,
        "key_terms": contract.key_terms,
        "special_terms": contract.special_terms,
        "file_path": contract.file_path,
    }
    
    # 调用AI审查
    ai_result = await review_contract_with_ai(contract_data, file_content)
    
    # 更新合同风险信息
    contract.risk_level = ai_result["risk_level"]
    contract.risk_score = ai_result["risk_score"]
    contract.risk_summary = ai_result["summary"]
    
    # 创建审查任务
    review_task = ReviewTask(
        contract_id=contract.id,
        reviewer_id=current_user.id,
        assigned_by=current_user.id,
        status=ReviewTaskStatus.COMPLETED,
        risk_level=ai_result["risk_level"],
        risk_score=ai_result["risk_score"],
        summary=ai_result["summary"],
        review_opinion=ai_result["summary"],
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.add(review_task)
    await db.flush()
    
    # 创建审查意见
    for finding in ai_result.get("findings", []):
        opinion = ReviewOpinion(
            review_task_id=review_task.id,
            reviewer_id=current_user.id,
            opinion_type=finding.get("category", "risk"),
            content=f"**{finding.get('title', '')}**\n\n{finding.get('description', '')}",
            suggestion=finding.get("suggestion"),
            risk_level=finding.get("risk_level"),
            clause_reference=finding.get("clause_reference"),
            legal_basis=finding.get("legal_basis"),
        )
        db.add(opinion)
    
    # 创建风险项（用于风险管理页面显示）
    from app.models.risk import RiskItem
    for finding in ai_result.get("findings", []):
        risk_item = RiskItem(
            contract_id=contract.id,
            review_task_id=review_task.id,
            title=finding.get("title", "未命名风险"),
            risk_description=finding.get("description", ""),
            risk_level=finding.get("risk_level", "medium"),
            risk_category=finding.get("category", "risk"),
            clause_reference=finding.get("clause_reference"),
            # 条款级定位信息
            clause_text=finding.get("clause_text"),
            clause_location=finding.get("clause_location"),
            confidence=finding.get("confidence", 0.8),
            suggestion=finding.get("suggestion"),
            legal_basis=finding.get("legal_basis"),
            is_resolved=False,
        )
        db.add(risk_item)
    
    # 更新合同状态
    contract.status = ContractStatus.REVIEWED
    contract.reviewed_at = datetime.utcnow()
    contract.reviewer_id = current_user.id
    
    await db.commit()
    await db.refresh(review_task)
    
    return {
        "message": "AI审查完成",
        "review_task_id": review_task.id,
        "risk_level": ai_result["risk_level"],
        "risk_score": ai_result["risk_score"],
        "summary": ai_result["summary"],
        "findings_count": len(ai_result.get("findings", [])),
    }


@router.post("/init-risk-items")
async def init_risk_items(
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """初始化已审查合同的风险项（补录历史数据）"""
    from app.models.risk import RiskItem
    
    # 获取所有已审查的合同
    result = await db.execute(
        select(Contract).where(Contract.status == ContractStatus.REVIEWED)
    )
    contracts = result.scalars().all()
    
    created_count = 0
    
    for contract in contracts:
        # 检查是否已有风险项
        existing = await db.execute(
            select(RiskItem).where(RiskItem.contract_id == contract.id)
        )
        if existing.scalars().first():
            continue
        
        # 从审查意见中创建风险项
        review_result = await db.execute(
            select(ReviewTask).where(ReviewTask.contract_id == contract.id)
        )
        review_task = review_result.scalars().first()
        
        if not review_task:
            continue
        
        opinions_result = await db.execute(
            select(ReviewOpinion).where(ReviewOpinion.review_task_id == review_task.id)
        )
        opinions = opinions_result.scalars().all()
        
        for opinion in opinions:
            # 从内容中提取标题
            content = opinion.content or ""
            title = content.split("\n")[0][:50] if content else "审查发现"
            
            risk_item = RiskItem(
                contract_id=contract.id,
                review_task_id=review_task.id,
                title=title,
                risk_description=content,
                risk_level=opinion.risk_level or "medium",
                risk_category=opinion.opinion_type if opinion.opinion_type else "risk",
                clause_reference=opinion.clause_reference,
                suggestion=opinion.suggestion,
                legal_basis=opinion.legal_basis,
                is_resolved=False,
            )
            db.add(risk_item)
            created_count += 1
    
    await db.commit()
    
    return {
        "message": f"成功创建{created_count}条风险项",
        "created_count": created_count,
        "processed_contracts": len(contracts),
    }


@router.post("/{contract_id}/modification-suggestions")
async def get_modification_suggestions(
    contract_id: int,
    review_task_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取合同修改建议"""
    from app.services.contract_modifier import contract_modifier
    
    # 验证合同存在
    contract = await db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    try:
        suggestions = await contract_modifier.generate_modification_suggestions(
            db, contract_id, review_task_id
        )
        return {
            "contract_id": contract_id,
            "suggestions": [asdict(s) for s in suggestions],
            "total": len(suggestions)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        import traceback
        print(f"生成修改建议错误: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成修改建议失败: {str(e) or '未知错误'}"
        )


@router.post("/{contract_id}/apply-modifications")
async def apply_modifications(
    contract_id: int,
    suggestion_ids: List[str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """应用修改建议"""
    from app.services.contract_modifier import contract_modifier
    
    # 验证合同存在
    contract = await db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    try:
        result = await contract_modifier.apply_modification(
            db, contract_id, suggestion_ids, current_user.id
        )
        return {
            "message": f"已应用 {result.applied_count} 个修改建议",
            "applied_count": result.applied_count,
            "total_suggestions": result.total_suggestions,
            "version_id": result.version_id,
            "modified_content": result.modified_content,
            "diff_summary": result.diff_summary
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"应用修改建议失败: {str(e)}"
        )


@router.get("/{contract_id}/export-modified")
async def export_modified_contract(
    contract_id: int,
    format: str = Query("word", regex="^(word|pdf|markdown)$"),
    version: str = Query("modified", regex="^(modified|clean|original)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出合同 - 修改版(含批注+对照表) / 清洁版 / 原文版"""
    from app.services.contract_modifier import contract_modifier
    from app.services.law_style_export import (
        generate_modified_docx, generate_clean_docx, generate_original_docx,
        generate_modified_pdf, generate_clean_pdf, generate_original_pdf,
    )
    from fastapi.responses import StreamingResponse
    import io, re, datetime
    
    contract = await db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    contract_title = contract.title or f"合同{contract_id}"
    contract_no = contract.contract_no or ""
    
    # 获取审查意见
    review_result = await db.execute(
        select(ReviewTask)
        .where(ReviewTask.contract_id == contract_id)
        .order_by(ReviewTask.created_at.desc())
        .limit(1)
    )
    review_task = review_result.scalar_one_or_none()
    
    suggestions = []
    sug_objs = []
    if review_task:
        findings_result = await db.execute(
            select(ReviewOpinion)
            .where(ReviewOpinion.review_task_id == review_task.id)
        )
        findings = findings_result.scalars().all()
        findings_list = [{
            "id": f.id,
            "clause": f.clause_reference or "",
            "content": f.content,
            "risk_level": f.risk_level or "medium",
            "category": f.opinion_type or "",
            "suggestion": f.suggestion or ""
        } for f in findings]
        sug_objs = contract_modifier._generate_with_rules(contract, findings_list)
        # 转成 dict 供 law_style_export 使用
        suggestions = [
            {
                "clause": s.clause,
                "original_text": s.original_text,
                "suggested_text": s.suggested_text,
                "reason": s.reason,
                "legal_basis": s.legal_basis,
                "risk_level": s.priority.value if hasattr(s.priority, 'value') else str(s.priority),
                "content": s.reason,
                "suggestion": s.suggested_text,
            }
            for s in sug_objs
        ]
    
    # 获取合同内容
    import os, hashlib
    cache_dir = f"/tmp/contract_export_cache"
    os.makedirs(cache_dir, exist_ok=True)
    # 缓存 key 包含合同更新时间 + 审查任务ID + 建议数量, 确保内容变化后重新生成
    contract_updated = contract.updated_at.isoformat() if hasattr(contract, 'updated_at') and contract.updated_at else ''
    cache_key = hashlib.md5(f"{contract_id}_{review_task.id if review_task else 0}_{len(suggestions)}_{contract_updated}".encode()).hexdigest()
    cache_file = f"{cache_dir}/{cache_key}.md"
    
    # AI 改写后的内容 (含开场白, 需清洗)
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            ai_content = f.read()
    elif review_task and sug_objs:
        # P0: 获取原始合同文本传给 AI
        orig_content = ""
        if contract.file_path:
            import os as _os
            if _os.path.exists(contract.file_path):
                try:
                    from app.services.file_parser import extract_text_from_file
                    orig_content = await extract_text_from_file(contract.file_path)
                except Exception:
                    pass
        # P1: timeout 120s
        try:
            import asyncio
            ai_content = await asyncio.wait_for(
                contract_modifier.rewrite_contract_with_ai(
                    contract, sug_objs, original_content=orig_content,
                    review_findings=findings_list
                ),
                timeout=120.0
            )
        except asyncio.TimeoutError:
            ai_content = contract_modifier._rewrite_with_rules(contract, sug_objs)
        with open(cache_file, "w") as f:
            f.write(ai_content)
    else:
        ai_content = contract_modifier._rewrite_with_rules(contract, [])
    
    # 清洗 AI 输出: 去掉开场白, 只保留 *** 后的正文
    def _clean_ai_output(text: str) -> str:
        if '***' in text:
            text = text.split('***', 1)[1].strip()
        # 也去掉可能残留的结尾废话
        text = re.sub(r'^(好的，|我将根据|根据您提供|为您生成).*?\n', '', text)
        # 去掉 markdown 代码块标记
        text = re.sub(r'^```(?:markdown)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
        return text.strip()
    
    modified_content = _clean_ai_output(ai_content)
    
    # 原始合同内容: 从文件解析
    original_content = None
    if contract.file_path and os.path.exists(contract.file_path):
        try:
            from app.services.file_parser import extract_text_from_file
            original_content = await extract_text_from_file(contract.file_path)
        except Exception:
            pass
    if not original_content:
        original_content = modified_content  # fallback
    
    risk_level = review_task.risk_level if review_task else ""
    
    # 根据 version 选择内容
    if version == "original":
        export_content = original_content
    else:
        export_content = modified_content
    
    # 专业文件名: 合同名_版本_日期.format
    date_str = datetime.date.today().strftime("%Y%m%d")
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', contract_title)[:30]
    version_label = {"modified": "修改版", "clean": "清洁版", "original": "原文版"}[version]
    ext = {"word": "docx", "pdf": "pdf", "markdown": "md"}[format]
    filename = f"{safe_title}_{version_label}_{date_str}.{ext}"
    
    # URL 编码文件名 (RFC 5987)
    from urllib.parse import quote
    filename_encoded = quote(filename)
    
    # 生成文件
    if format == "markdown":
        return StreamingResponse(
            io.BytesIO(export_content.encode("utf-8")),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=contract_{contract_id}.{ext}; filename*=UTF-8''{filename_encoded}"}
        )
    
    if format == "word":
        if version == "modified":
            file_bytes = generate_modified_docx(export_content, suggestions, contract_title, contract_no, risk_level=risk_level)
        elif version == "clean":
            file_bytes = generate_clean_docx(export_content, contract_title, contract_no, risk_level=risk_level)
        else:
            file_bytes = generate_original_docx(export_content, contract_title, contract_no)
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=contract_{contract_id}.{ext}; filename*=UTF-8''{filename_encoded}"}
        )
    
    if format == "pdf":
        if version == "modified":
            file_bytes = generate_modified_pdf(export_content, suggestions, contract_title, contract_no)
        elif version == "clean":
            file_bytes = generate_clean_pdf(export_content, contract_title, contract_no)
        else:
            file_bytes = generate_original_pdf(export_content, contract_title, contract_no)
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=contract_{contract_id}.{ext}; filename*=UTF-8''{filename_encoded}"}
        )


@router.get("/{contract_id}/versions")
async def get_contract_versions(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取合同版本历史"""
    # 验证合同存在
    contract = await db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    result = await db.execute(
        select(ContractVersion)
        .where(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_no.desc())
    )
    versions = result.scalars().all()
    
    return {
        "contract_id": contract_id,
        "versions": [
            {
                "id": v.id,
                "version_no": v.version_no,
                "change_summary": v.change_summary,
                "created_at": v.created_at.isoformat() if v.created_at else None
            }
            for v in versions
        ]
    }


@router.get("/{contract_id}/versions/compare")
async def compare_versions(
    contract_id: int,
    version1_id: int = Query(..., description="版本1 ID"),
    version2_id: int = Query(..., description="版本2 ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对比两个版本的差异"""
    from app.services.contract_modifier import version_comparer
    
    try:
        result = await version_comparer.compare_versions(
            db, contract_id, version1_id, version2_id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"版本对比失败: {str(e)}"
        )


@router.get("/{contract_id}/compare-original")
async def compare_with_original(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对比原合同和修改后合同"""
    from app.services.contract_modifier import contract_modifier
    from app.services.file_parser import extract_text_from_file
    
    # 获取合同
    contract = await db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    # 获取原合同内容 - 从文件中提取
    original_content = None
    if contract.file_path:
        try:
            original_content = await extract_text_from_file(contract.file_path)
        except Exception as e:
            print(f"提取原合同文件内容失败: {e}")
    
    # 如果无法从文件提取，使用AI生成基础合同内容
    if not original_content:
        # 使用规则引擎生成基础合同（不包含修改建议）
        original_content = contract_modifier._rewrite_with_rules(contract, [])
    
    # 获取最新版本的修改后内容
    result = await db.execute(
        select(ContractVersion)
        .where(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_no.desc())
        .limit(1)
    )
    latest_version = result.scalar_one_or_none()
    
    modified_content = None
    if latest_version:
        # 获取审查发现来重新生成修改后内容
        review_result = await db.execute(
            select(ReviewTask)
            .where(ReviewTask.contract_id == contract_id)
            .order_by(ReviewTask.created_at.desc())
            .limit(1)
        )
        review_task = review_result.scalar_one_or_none()
        
        if review_task:
            findings_result = await db.execute(
                select(ReviewOpinion)
                .where(ReviewOpinion.review_task_id == review_task.id)
            )
            findings = findings_result.scalars().all()
            
            findings_list = [{
                "id": f.id,
                "clause": f.clause_reference or "",
                "content": f.content,
                "risk_level": f.risk_level or "medium",
                "category": f.opinion_type or "",
                "suggestion": f.suggestion or ""
            } for f in findings]
            suggestions = contract_modifier._generate_with_rules(contract, findings_list)
            modified_content = await contract_modifier.rewrite_contract_with_ai(
                contract, suggestions, review_findings=findings_list
            )
    
    return {
        "contract_id": contract_id,
        "contract_title": contract.title,
        "original_content": original_content,
        "modified_content": modified_content,
        "has_modifications": modified_content is not None,
        "version_no": latest_version.version_no if latest_version else None
    }


@router.post("/batch-review")
async def batch_review_contracts(
    contract_ids: List[int],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量审查合同"""
    # 验证合同存在
    for contract_id in contract_ids:
        contract = await db.get(Contract, contract_id)
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"合同 {contract_id} 不存在",
            )
    
    # 启动后台任务
    background_tasks.add_task(
        _batch_review_task,
        contract_ids,
        current_user.id
    )
    
    return {
        "message": f"已启动批量审查任务，共 {len(contract_ids)} 个合同",
        "contract_ids": contract_ids,
        "status": "processing"
    }


async def _batch_review_task(contract_ids: List[int], user_id: int):
    """批量审查后台任务"""
    from app.core.database import AsyncSessionLocal
    
    results = {"success": [], "failed": []}
    
    async with AsyncSessionLocal() as db:
        for contract_id in contract_ids:
            try:
                # 获取合同
                contract = await db.get(Contract, contract_id)
                if not contract:
                    results["failed"].append({"id": contract_id, "error": "合同不存在"})
                    continue
                
                # 构建合同数据
                contract_data = {
                    "title": contract.title,
                    "contract_type": contract.contract_type.value if contract.contract_type else "other",
                    "party_a": contract.party_a,
                    "party_b": contract.party_b,
                    "amount": float(contract.amount) if contract.amount else None,
                    "currency": contract.currency,
                    "description": contract.description,
                    "key_terms": contract.key_terms,
                    "special_terms": contract.special_terms,
                }
                
                # 提取文件内容
                file_content = None
                if contract.file_path:
                    file_content = await extract_file_content(contract.file_path)
                
                # AI审查
                ai_result = await review_contract_with_ai(contract_data, file_content)
                
                # 更新合同
                contract.risk_level = ai_result["risk_level"]
                contract.risk_score = ai_result["risk_score"]
                contract.risk_summary = ai_result["summary"]
                
                # 创建审查任务
                review_task = ReviewTask(
                    contract_id=contract.id,
                    reviewer_id=user_id,
                    assigned_by=user_id,
                    status=ReviewTaskStatus.COMPLETED,
                    risk_level=ai_result["risk_level"],
                    risk_score=ai_result["risk_score"],
                    summary=ai_result["summary"],
                    review_opinion=ai_result["summary"],
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                )
                db.add(review_task)
                await db.flush()
                
                # 创建审查意见
                for finding in ai_result.get("findings", []):
                    opinion = ReviewOpinion(
                        review_task_id=review_task.id,
                        reviewer_id=user_id,
                        opinion_type=finding.get("category", "risk"),
                        content=f"**{finding.get('title', '')}**\n\n{finding.get('description', '')}",
                        suggestion=finding.get("suggestion"),
                        risk_level=finding.get("risk_level"),
                        clause_reference=finding.get("clause_reference"),
                        legal_basis=finding.get("legal_basis"),
                    )
                    db.add(opinion)
                
                # 创建风险项
                for finding in ai_result.get("findings", []):
                    risk_item = RiskItem(
                        contract_id=contract.id,
                        review_task_id=review_task.id,
                        title=finding.get("title", "未命名风险"),
                        risk_description=finding.get("description", ""),
                        risk_level=finding.get("risk_level", "medium"),
                        risk_category=finding.get("category", "risk"),
                        clause_reference=finding.get("clause_reference"),
                        clause_text=finding.get("clause_text"),
                        clause_location=finding.get("clause_location"),
                        confidence=finding.get("confidence", 0.8),
                        suggestion=finding.get("suggestion"),
                        legal_basis=finding.get("legal_basis"),
                        is_resolved=False,
                    )
                    db.add(risk_item)
                
                # 更新状态
                contract.status = ContractStatus.REVIEWED
                contract.reviewed_at = datetime.utcnow()
                contract.reviewer_id = user_id
                
                await db.commit()
                
                results["success"].append({
                    "id": contract_id,
                    "title": contract.title,
                    "risk_level": ai_result.get("risk_level", "medium"),
                    "risk_score": ai_result.get("risk_score", 0),
                    "findings_count": len(ai_result.get("findings", []))
                })
                
            except Exception as e:
                await db.rollback()
                results["failed"].append({"id": contract_id, "error": str(e)})
                continue

    print(f"批量审查完成: 成功 {len(results['success'])} 个, 失败 {len(results['failed'])} 个")
    return results



