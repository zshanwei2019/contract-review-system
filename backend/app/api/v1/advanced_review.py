"""
高级 AI 审查 API
- 条款级审查 (含义务提取 + 谈判策略)
- 语义比对
- 相对方画像
- 外部风险评估
- 双语合同审查
- 法规动态更新
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


# ========== P3: 双语合同审查 + 法规动态更新 ==========

@router.post("/contracts/bilingual-review")
async def bilingual_review(
    cn_text: str = Body(..., description="中文合同文本"),
    en_text: str = Body(..., description="英文合同文本"),
    contract_type: str = Body("other", description="合同类型"),
    current_user: User = Depends(get_current_user),
):
    """
    双语合同审查
    中英文段落对齐 + 术语一致性 + 条款内容对比 + 语言优先级检查
    """
    from app.services.bilingual_review import review_bilingual_contract

    result = review_bilingual_contract(cn_text, en_text, contract_type)
    return result


@router.post("/contracts/{contract_id}/bilingual-review")
async def bilingual_review_by_contract(
    contract_id: int,
    cn_text: Optional[str] = Body(None, description="中文合同文本(可选,默认从文件提取)"),
    en_text: Optional[str] = Body(None, description="英文合同文本(可选,默认从文件提取)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    双语合同审查 (按合同ID)
    """
    from app.services.bilingual_review import review_bilingual_contract
    from app.services.file_parser import extract_text_from_file

    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 尝试从文件提取
    if not cn_text and contract.file_path:
        import os
        fp = contract.file_path
        if not os.path.isabs(fp):
            fp = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), fp)
        # 中英文文件路径: 尝试 _cn / _en 后缀
        cn_path = fp.replace(".docx", "_cn.docx").replace(".pdf", "_cn.pdf")
        en_path = fp.replace(".docx", "_en.docx").replace(".pdf", "_en.pdf")
        if os.path.exists(cn_path):
            cn_text = await extract_text_from_file(cn_path)
        if os.path.exists(en_path):
            en_text = await extract_text_from_file(en_path)

    if not cn_text or not en_text:
        raise HTTPException(status_code=400, detail="需要同时提供中文和英文合同文本")

    ct = contract.contract_type.value if contract.contract_type else "other"
    result = review_bilingual_contract(cn_text, en_text, ct)
    return result


@router.post("/contracts/compliance-check")
async def compliance_check(
    contract_text: str = Body(..., description="合同文本"),
    contract_type: str = Body("other", description="合同类型"),
    current_user: User = Depends(get_current_user),
):
    """
    法规合规性检查
    基于最新法规(民法典/公司法/劳动法等)检查合同条款合规性
    """
    from app.services.regulation_updater import check_full_contract_compliance

    result = check_full_contract_compliance(contract_text, contract_type)
    return result


@router.post("/contracts/{contract_id}/compliance-check")
async def compliance_check_by_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    法规合规性检查 (按合同ID)
    """
    from app.services.regulation_updater import check_full_contract_compliance
    from app.services.file_parser import extract_text_from_file

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

    ct = contract.contract_type.value if contract.contract_type else "other"
    result = check_full_contract_compliance(full_text, ct)
    return result


@router.get("/regulations/search")
async def search_regulations_api(
    query: str = Query(..., description="搜索关键词"),
    category: Optional[str] = Query(None, description="法规分类: civil/commercial/labor/tax/ip"),
    current_user: User = Depends(get_current_user),
):
    """
    搜索相关法规
    """
    from app.services.regulation_updater import search_regulations

    regs = search_regulations(query, category)
    return {
        "query": query,
        "count": len(regs),
        "results": [
            {
                "id": r.id,
                "name": r.name,
                "article": r.article,
                "content": r.content,
                "category": r.category,
                "effective_date": r.effective_date,
                "status": r.status,
                "keywords": r.keywords,
            }
            for r in regs
        ],
    }


@router.get("/regulations/updates")
async def get_regulation_updates_api(
    since_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
):
    """
    获取法规变更列表
    """
    from app.services.regulation_updater import get_regulation_updates

    updates = get_regulation_updates(since_date)
    return {
        "since_date": since_date or "6 months ago",
        "count": len(updates),
        "updates": updates,
    }


@router.post("/contracts/regulation-impact")
async def assess_regulation_impact_api(
    contract_text: str = Body(..., description="合同文本"),
    contract_type: str = Body("other", description="合同类型"),
    current_user: User = Depends(get_current_user),
):
    """
    评估法规变更对合同的影响
    """
    from app.services.regulation_updater import assess_regulation_impact

    result = assess_regulation_impact(contract_text, contract_type)
    return result
