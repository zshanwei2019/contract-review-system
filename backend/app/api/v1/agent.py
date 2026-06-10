"""
Agent智能体 API
5-Agent协作 + 风控规则 + 合规追踪 + 报告导出 + 自学习
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import io

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.contract import Contract, ContractStatus
from app.models.review import ReviewTask, ReviewTaskStatus
from app.models.memory import ReviewCase, CorrectionLog

from app.services.multi_agent import run_multi_agent_review, merge_agent_results, save_agent_messages, AGENT_ROLES
from app.services.chain import AgentChain, search_knowledge_tool, get_risk_patterns_tool, get_similar_cases_tool, verify_party_info_tool, Tool
from app.services.monitoring import generate_monitoring_alerts
from app.services.knowledge import search_laws_for_contract, get_compliance_rules, init_builtin_knowledge
from app.services.memory import get_similar_cases, get_risk_patterns_for_type
from app.services.feedback import submit_correction, rate_review_case, get_correction_stats
from app.services.risk_rules_engine import full_risk_analysis, check_industry_risks, detect_poison_pills, INDUSTRY_RISK_RULES, POISON_PILL_PATTERNS, RISK_DIMENSIONS
from app.services.clause_segmenter import segment_clauses, analyze_clause_risks, get_clause_summary
from app.services.compliance_tracker import evaluate_compliance, get_checklist, generate_rectification_plan
from app.services.report_export import generate_word_report, generate_pdf_report
from app.services.vector_index import search_similar_contracts, search_similar_findings, index_contract, get_vector_index
from app.services.self_learning import learn_from_corrections, get_learning_stats, run_fp_growth

from sqlalchemy import select
import json
from datetime import datetime

router = APIRouter()


# ==================== 多Agent审查 ====================

@router.post("/multi-agent-review/{contract_id}")
async def multi_agent_review(
    contract_id: int,
    agents: Optional[List[str]] = Query(None, description="指定Agent列表"),
    current_user: User = Depends(require_role("admin", "superadmin", "legal_manager", "legal_specialist")),
    db: AsyncSession = Depends(get_db),
):
    """5-Agent协作审查"""
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    agent_results = await run_multi_agent_review(db, contract, agents)
    merged = await merge_agent_results(agent_results)

    # 创建审查任务
    review_task = ReviewTask(
        contract_id=contract.id,
        reviewer_id=current_user.id,
        assigned_by=current_user.id,
        status=ReviewTaskStatus.COMPLETED,
        risk_level=merged["risk_level"],
        risk_score=merged["risk_score"],
        summary=merged["summary"],
        review_opinion=json.dumps(merged, ensure_ascii=False),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.add(review_task)
    await db.flush()

    # 保存各Agent发现
    from app.models.review import ReviewOpinion
    for agent_id, result in agent_results.items():
        agent_name = AGENT_ROLES.get(agent_id, {}).get("name", agent_id)
        for finding in result.get("findings", []):
            opinion = ReviewOpinion(
                review_task_id=review_task.id,
                reviewer_id=current_user.id,
                opinion_type=f"{agent_id}:{finding.get('category', 'other')}",
                content=f"[{agent_name}] {finding.get('title', '')}\n\n{finding.get('description', '')}",
                suggestion=finding.get("suggestion"),
                risk_level=finding.get("risk_level"),
            )
            db.add(opinion)

    # 保存审查案例
    case = ReviewCase(
        contract_id=contract.id,
        contract_type=contract.contract_type.value if contract.contract_type else "other",
        contract_title=contract.title,
        amount=float(contract.amount) if contract.amount else None,
        risk_level=merged["risk_level"],
        risk_score=merged["risk_score"],
        key_findings=json.dumps([f for r in agent_results.values() for f in r.get("findings", [])], ensure_ascii=False),
        review_summary=merged["summary"],
        is_ai_review=True,
        ai_model="5-agent",
        reviewer_id=current_user.id,
    )
    db.add(case)

    # 索引到向量库
    await index_contract(contract.id, merged["summary"], {"contract_type": contract.contract_type.value if contract.contract_type else "other"})

    contract.status = ContractStatus.REVIEWED
    contract.reviewed_at = datetime.utcnow()
    contract.reviewer_id = current_user.id
    contract.risk_level = merged["risk_level"]
    contract.risk_score = merged["risk_score"]

    await db.commit()

    return {
        "message": "5-Agent审查完成",
        "review_task_id": review_task.id,
        "case_id": case.id,
        "merged_result": merged,
    }


# ==================== 推理链审查 ====================

@router.post("/chain-review/{contract_id}")
async def chain_review(
    contract_id: int,
    current_user: User = Depends(require_role("admin", "superadmin", "legal_manager")),
    db: AsyncSession = Depends(get_db),
):
    """多步推理链审查"""
    from app.core.config import settings

    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="需要配置OPENAI_API_KEY")

    tools = [
        Tool(
            name="search_knowledge",
            description="搜索法律法规和企业合规规则",
            func=lambda keyword, contract_type="all": search_knowledge_tool(keyword, contract_type, db=db),
            parameters={"type": "object", "properties": {"keyword": {"type": "string"}, "contract_type": {"type": "string"}}, "required": ["keyword"]},
        ),
        Tool(
            name="get_risk_patterns",
            description="获取该类型合同的历史风险模式",
            func=lambda contract_type: get_risk_patterns_tool(contract_type, db=db),
            parameters={"type": "object", "properties": {"contract_type": {"type": "string"}}, "required": ["contract_type"]},
        ),
        Tool(
            name="get_similar_cases",
            description="获取相似合同的历史审查案例",
            func=lambda contract_type, risk_level=None: get_similar_cases_tool(contract_type, risk_level, db=db),
            parameters={"type": "object", "properties": {"contract_type": {"type": "string"}, "risk_level": {"type": "string"}}, "required": ["contract_type"]},
        ),
        Tool(
            name="verify_party",
            description="验证合同主体工商信息",
            func=lambda party_name: verify_party_info_tool(party_name),
            parameters={"type": "object", "properties": {"party_name": {"type": "string"}}, "required": ["party_name"]},
        ),
    ]

    contract_data = {
        "title": contract.title,
        "contract_type": contract.contract_type.value if contract.contract_type else "",
        "party_a": contract.party_a,
        "party_b": contract.party_b,
        "amount": str(contract.amount) if contract.amount else None,
    }

    task = f"对合同「{contract.title}」进行全面法律风险审查。"
    chain = AgentChain(tools=tools, max_steps=8)
    chain_result = await chain.run(task, contract_data)

    if not chain_result["success"]:
        raise HTTPException(status_code=500, detail=f"推理链执行失败: {chain_result.get('error')}")

    return {"message": "推理链审查完成", "result": chain_result}


# ==================== 风控规则 ====================

@router.get("/risk-rules")
async def list_risk_rules(
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """列出23条行业风控规则"""
    rules = INDUSTRY_RISK_RULES
    if category:
        rules = [r for r in rules if category in r["cat"]]
    return {
        "rules": [{"id": r["id"], "name": r["name"], "category": r["cat"], "severity": r["sev"], "description": r["desc"]} for r in rules],
        "total": len(rules),
    }


@router.get("/risk-rules/poison-pills")
async def list_poison_pills(
    current_user: User = Depends(get_current_user),
):
    """列出14种毒丸条款检测模式"""
    return {
        "patterns": [{"id": p["id"], "name": p["name"], "type": p["type"], "severity": p["sev"]} for p in POISON_PILL_PATTERNS],
        "total": len(POISON_PILL_PATTERNS),
    }


@router.post("/risk-rules/analyze")
async def analyze_with_rules(
    text: str,
    contract_category: str = Query("all"),
    current_user: User = Depends(get_current_user),
):
    """使用风控规则引擎分析文本"""
    analysis = full_risk_analysis(text, contract_category)
    return analysis


@router.get("/risk-rules/dimensions")
async def get_risk_dimensions(
    current_user: User = Depends(get_current_user),
):
    """获取四维加权风险评估模型"""
    return {"dimensions": RISK_DIMENSIONS}


# ==================== 条款分割 ====================

@router.post("/clause-segment/{contract_id}")
async def segment_contract_clauses(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """合同条款分割与分析"""
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    from app.services.ai_review import extract_file_content
    text = ""
    if contract.file_path:
        text = await extract_file_content(contract.file_path)
    if not text:
        text = contract.description or ""

    clauses = segment_clauses(text)
    clauses = analyze_clause_risks(clauses)
    summary = get_clause_summary(clauses)

    return {"clauses": clauses, "summary": summary}


# ==================== 合规追踪 ====================

@router.post("/compliance/check/{contract_id}")
async def check_compliance(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """合规性检查"""
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 获取审查发现
    review_result = await db.execute(
        select(ReviewTask).where(ReviewTask.contract_id == contract_id).order_by(ReviewTask.created_at.desc()).limit(1)
    )
    review_task = review_result.scalar_one_or_none()

    findings = []
    if review_task and review_task.review_opinion:
        try:
            opinion = json.loads(review_task.review_opinion)
            findings = opinion.get("findings", [])
        except (json.JSONDecodeError, TypeError):
            pass

    contract_type = contract.contract_type.value if contract.contract_type else "other"
    compliance = evaluate_compliance(contract_type, findings)
    rectification = generate_rectification_plan(compliance)

    return {"compliance": compliance, "rectification_plan": rectification}


@router.get("/compliance/checklist/{contract_type}")
async def get_compliance_checklist(
    contract_type: str,
    current_user: User = Depends(get_current_user),
):
    """获取合规检查清单"""
    checklist = get_checklist(contract_type)
    return {"contract_type": contract_type, "checklist": checklist}


# ==================== 报告导出 ====================

@router.get("/report/export/{contract_id}")
async def export_report(
    contract_id: int,
    format: str = Query("word", regex="^(word|pdf)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出审查报告（Word/PDF）"""
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 获取审查结果
    review_result = await db.execute(
        select(ReviewTask).where(ReviewTask.contract_id == contract_id).order_by(ReviewTask.created_at.desc()).limit(1)
    )
    review_task = review_result.scalar_one_or_none()

    review_data = {}
    if review_task and review_task.review_opinion:
        try:
            review_data = json.loads(review_task.review_opinion)
        except (json.JSONDecodeError, TypeError):
            pass

    if not review_data:
        review_data = {"risk_level": contract.risk_level or "low", "risk_score": contract.risk_score or 0, "summary": "暂无审查结果"}

    contract_data = {
        "title": contract.title,
        "contract_type": contract.contract_type.value if contract.contract_type else "",
        "party_a": contract.party_a,
        "party_b": contract.party_b,
        "amount": str(contract.amount) if contract.amount else None,
        "currency": contract.currency,
        "sign_date": str(contract.sign_date) if contract.sign_date else None,
        "effective_date": str(contract.effective_date) if contract.effective_date else None,
        "expiry_date": str(contract.expiry_date) if contract.expiry_date else None,
    }

    if format == "word":
        content = generate_word_report(review_data, contract_data)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"审查报告_{contract.title}.docx"
    else:
        content = generate_pdf_report(review_data, contract_data)
        media_type = "application/pdf"
        filename = f"审查报告_{contract.title}.pdf"

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


# ==================== 向量检索 ====================

@router.get("/search/contracts")
async def search_contracts_vector(
    query: str = Query(...),
    top_k: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
):
    """向量相似度搜索合同"""
    results = await search_similar_contracts(query, top_k)
    return {"results": results, "total": len(results)}


@router.get("/search/findings")
async def search_findings_vector(
    query: str = Query(...),
    top_k: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
):
    """向量相似度搜索审查发现"""
    results = await search_similar_findings(query, top_k)
    return {"results": results, "total": len(results)}


# ==================== 自学习 ====================

@router.post("/learning/learn")
async def trigger_learning(
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """触发自学习（从人工纠正中学习）"""
    result = await learn_from_corrections(db, limit)
    return result


@router.get("/learning/stats")
async def learning_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取自学习统计"""
    stats = await get_learning_stats(db)
    return stats


@router.get("/learning/fp-growth")
async def fp_growth_analysis(
    min_support: int = Query(2, ge=1),
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """FP-Growth关联规则挖掘"""
    rules = await run_fp_growth(db, min_support)
    return {"rules": rules, "total": len(rules)}


# ==================== 监控告警 ====================

@router.get("/monitoring/alerts")
async def get_monitoring_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取监控告警"""
    alerts = await generate_monitoring_alerts(db)
    return alerts


# ==================== 知识库 ====================

@router.get("/knowledge/laws")
async def get_laws(
    contract_type: str = Query("all"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取适用的法律法规"""
    laws = await search_laws_for_contract(db, contract_type)
    return {"items": laws, "total": len(laws)}


@router.get("/knowledge/compliance")
async def get_compliance(
    contract_type: str = Query("all"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取企业合规规则"""
    rules = await get_compliance_rules(db, contract_type)
    return {"items": rules, "total": len(rules)}


@router.post("/knowledge/init")
async def init_knowledge(
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """初始化内置知识库"""
    await init_builtin_knowledge(db)
    return {"message": "知识库初始化完成"}


# ==================== 案例与反馈 ====================

@router.get("/cases/similar")
async def get_similar(
    contract_type: str = Query(...),
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),    db: AsyncSession = Depends(get_db),
):
    """获取相似案例"""
    cases = await get_similar_cases(db, contract_type, limit)
    return {
        "items": [
            {
                "id": c.id,
                "contract_title": c.contract_title,
                "risk_level": c.risk_level,
                "risk_score": c.risk_score,
                "summary": c.review_summary,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in cases
        ],
        "total": len(cases),
    }


@router.get("/cases/{case_id}")
async def get_case_detail(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取案例详情"""
    result = await db.execute(select(ReviewCase).where(ReviewCase.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    return case


@router.post("/cases/{case_id}/rate")
async def rate_case(
    case_id: int,
    rating: int = Query(..., ge=1, le=5),
    comment: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对案例评分"""
    case = await rate_review_case(db, case_id, current_user.id, rating, comment)
    return {"message": "评分成功", "case_id": case.id, "rating": case.human_rating}


@router.post("/corrections")
async def create_correction(
    review_case_id: int,
    original_opinion_id: Optional[int] = None,
    corrected_opinion: str = "",
    correction_reason: str = "",
    correction_type: str = "modify",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交人工修正"""
    correction = await submit_correction(
        db, review_case_id, current_user.id,
        original_opinion_id, corrected_opinion, correction_reason, correction_type,
    )
    return {"message": "修正已提交", "correction_id": correction.id}


@router.get("/corrections/stats")
async def correction_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取修正统计"""
    stats = await get_correction_stats(db)
    return stats


@router.get("/agents")
async def list_agents(
    current_user: User = Depends(get_current_user),
):
    """列出所有Agent"""
    return {
        "agents": [
            {"id": k, "name": v["name"], "icon": v["icon"], "focus": v["focus"], "weight": v.get("weight", 0)}
            for k, v in AGENT_ROLES.items()
        ]
    }
