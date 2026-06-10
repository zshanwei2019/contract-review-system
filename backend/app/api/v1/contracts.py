from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
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
    contract_data: ContractCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建合同"""
    contract = Contract(
        contract_no=generate_contract_no(),
        title=contract_data.title,
        contract_type=contract_data.contract_type,
        party_a=contract_data.party_a,
        party_b=contract_data.party_b,
        amount=contract_data.amount,
        currency=contract_data.currency,
        sign_date=contract_data.sign_date,
        effective_date=contract_data.effective_date,
        expiry_date=contract_data.expiry_date,
        description=contract_data.description,
        department=contract_data.department,
        project_name=contract_data.project_name,
        tags=contract_data.tags,
        uploader_id=current_user.id,
        status=ContractStatus.DRAFT,
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    
    return contract


@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    contract_type: Optional[ContractType] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传合同文件"""
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
    
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(upload_dir, file_name)
    
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Create contract
    contract_title = title or file.filename
    contract = Contract(
        contract_no=generate_contract_no(),
        title=contract_title,
        contract_type=contract_type or ContractType.OTHER,
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
        message="合同上传成功",
    )


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
