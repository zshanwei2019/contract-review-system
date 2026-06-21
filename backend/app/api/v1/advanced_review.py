"""
高级 AI 审查 API
- 条款级审查 (含义务提取 + 谈判策略)
- 语义比对
- 相对方画像
- 外部风险评估
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List, Dict

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.contract import Contract

router = APIRouter()


@router.post("/contracts/{contract_id}/clause-review")
async def clause_review(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    条款级深度审查 (含义务提取 + 谈判策略)
    返回: 逐条款风险分析 + 义务清单 + 谈判策略
    """
    from app.services.clause_review_service import get_clause_review_service
    from app.services.file_parser import extract_text_from_file

    # 获取合同
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 提取合同文本
    full_text = ""
    if contract.file_path:
        import os
        fp = contract.file_path
        if not os.path.isabs(fp):
            # 相对路径基于 backend 目录解析
            fp = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), fp)
        if os.path.exists(fp):
            full_text = await extract_text_from_file(fp)

    if not full_text:
        # 尝试从合同字段构建文本
        parts = [contract.title or ""]
        if contract.description:
            parts.append(contract.description)
        if contract.key_terms:
            parts.append(contract.key_terms)
        if contract.special_terms:
            parts.append(contract.special_terms)
        full_text = "\n\n".join(parts)

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="合同内容为空，无法审查")

    # 执行条款级审查
    service = get_clause_review_service()
    review = await service.review_contract_by_clauses(
        contract_text=full_text,
        contract_type=contract.contract_type.value if contract.contract_type else "other",
        contract_id=contract_id,
    )

    return service.to_dict(review)


@router.post("/contracts/compare")
async def compare_contracts(
    original_text: str = Body(..., description="原始合同文本"),
    revised_text: str = Body(..., description="修改后合同文本"),
    current_user: User = Depends(get_current_user),
):
    """
    合同语义比对 (Semantic Diff)
    对比两份合同文本，识别实质性修改 vs 格式调整
    """
    from app.services.semantic_diff import compare_contracts as semantic_compare

    result = semantic_compare(original_text, revised_text)
    return result


@router.post("/contracts/{contract_id}/compare-versions")
async def compare_contract_versions(
    contract_id: int,
    version_a: int = Body(..., description="版本A编号"),
    version_b: int = Body(..., description="版本B编号"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    比对合同的两个历史版本
    """
    from app.models.contract import ContractVersion
    from app.services.semantic_diff import compare_contracts as semantic_compare

    # 获取两个版本
    result = await db.execute(
        select(ContractVersion).where(
            ContractVersion.contract_id == contract_id,
            ContractVersion.version_no.in_([version_a, version_b])
        )
    )
    versions = {v.version_no: v for v in result.scalars().all()}

    if version_a not in versions or version_b not in versions:
        raise HTTPException(status_code=404, detail="版本不存在")

    text_a = versions[version_a].content or ""
    text_b = versions[version_b].content or ""

    if not text_a or not text_b:
        raise HTTPException(status_code=400, detail="版本内容为空")

    result = semantic_compare(text_a, text_b)
    result["version_a"] = version_a
    result["version_b"] = version_b
    return result


@router.get("/parties/{party_name}/profile")
async def get_party_profile(
    party_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    相对方画像分析
    基于历史合同数据分析对方的风险等级、谈判风格、条款偏好
    """
    from app.services.party_profiler import analyze_party

    # 获取该相对方的历史合同
    result = await db.execute(
        select(Contract).where(
            (Contract.party_a.contains(party_name)) |
            (Contract.party_b.contains(party_name))
        ).order_by(Contract.created_at.desc()).limit(20)
    )
    contracts = result.scalars().all()

    history = []
    for c in contracts:
        history.append({
            "contract_id": c.id,
            "title": c.title,
            "contract_type": c.contract_type.value if c.contract_type else "",
            "party_a": c.party_a or "",
            "party_b": c.party_b or "",
            "amount": float(c.amount) if c.amount else 0,
            "risk_level": c.risk_level or "",
            "risk_score": c.risk_score or 0,
            "status": c.status.value if c.status else "",
            "created_at": c.created_at.isoformat() if c.created_at else "",
        })

    profile = analyze_party(party_name, history)
    return profile


@router.get("/parties/{party_name}/external-risk")
async def get_external_risk(
    party_name: str,
    internal_risk_score: float = Query(0.0, description="内部审查风险分"),
    current_user: User = Depends(get_current_user),
):
    """
    外部风险评估 (工商信息 + 司法风险)
    综合内部审查分 + 外部数据分
    """
    from app.services.external_data import assess_external_risk

    result = assess_external_risk(
        company_name=party_name,
        internal_risk_score=internal_risk_score,
    )
    return result


@router.get("/contracts/{contract_id}/obligations")
async def get_contract_obligations(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    提取合同义务清单 + 履约跟踪
    """
    from app.services.obligation_extractor import extract_obligations
    from app.services.file_parser import extract_text_from_file
    from app.services.clause_segmenter import segment_clauses

    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    full_text = ""
    if contract.file_path:
        import os
        fp = contract.file_path
        if not os.path.isabs(fp):
            fp = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), fp)
        if os.path.exists(fp):
            full_text = await extract_text_from_file(fp)

    if not full_text:
        raise HTTPException(status_code=400, detail="合同内容为空")

    # 先分段
    clauses = segment_clauses(full_text)
    obligations = extract_obligations(clauses)
    return obligations


@router.get("/contracts/{contract_id}/playbook")
async def get_negotiation_playbook(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    生成谈判策略手册
    基于审查发现生成谈判立场、话术、交换条件
    """
    from app.services.playbook_generator import generate_playbook
    from app.models.review import ReviewTask, ReviewOpinion

    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 获取审查发现
    review_result = await db.execute(
        select(ReviewTask).where(ReviewTask.contract_id == contract_id)
        .order_by(ReviewTask.created_at.desc()).limit(1)
    )
    review_task = review_result.scalar_one_or_none()

    findings = []
    if review_task:
        opinions_result = await db.execute(
            select(ReviewOpinion).where(ReviewOpinion.review_task_id == review_task.id)
        )
        for op in opinions_result.scalars().all():
            findings.append({
                "clause_title": op.clause_reference or "未指定条款",
                "description": op.content or "",
                "severity": op.risk_level or "medium",
                "risk_score": 50 if op.risk_level == "high" else (30 if op.risk_level == "medium" else 10),
            })

    if not findings:
        raise HTTPException(status_code=400, detail="未找到审查发现，请先执行审查")

    playbook = generate_playbook(findings)
    return playbook
