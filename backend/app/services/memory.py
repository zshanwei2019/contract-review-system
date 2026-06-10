"""
记忆系统 - 审查案例库 + 风险模式积累
"""

import json
import logging
from typing import Optional, List, Dict
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.memory import (
    ReviewCase, RiskPattern, ContractKnowledge,
    PatternSeverity, KnowledgeType,
)
from app.models.contract import Contract
from app.models.review import ReviewTask, ReviewOpinion

logger = logging.getLogger(__name__)


async def save_review_case(
    db: AsyncSession,
    contract: Contract,
    review_task: ReviewTask,
    opinions: List[ReviewOpinion],
    ai_result: dict,
    corrections: Optional[List[dict]] = None,
) -> ReviewCase:
    """保存审查案例到记忆库"""
    # 提取关键信息
    key_findings = []
    for op in opinions:
        key_findings.append({
            "type": op.opinion_type,
            "content": op.content[:200],
            "risk_level": op.risk_level,
            "suggestion": op.suggestion[:200] if op.suggestion else None,
        })
    
    # 构造经验总结
    lessons = []
    if corrections:
        for c in corrections:
            lessons.append({
                "original": c.get("original"),
                "correction": c.get("correction"),
                "reason": c.get("reason"),
            })
    
    case = ReviewCase(
        contract_id=contract.id,
        contract_type=contract.contract_type.value if contract.contract_type else "other",
        contract_title=contract.title,
        amount=float(contract.amount) if contract.amount else None,
        risk_level=review_task.risk_level,
        risk_score=review_task.risk_score,
        key_findings=json.dumps(key_findings, ensure_ascii=False),
        review_summary=review_task.summary,
        lessons_learned=json.dumps(lessons, ensure_ascii=False) if lessons else None,
        reviewer_id=review_task.reviewer_id,
        is_ai_review=True,
        ai_model=ai_result.get("model"),
        ai_confidence=ai_result.get("confidence"),
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    
    logger.info(f"审查案例已保存: case_id={case.id}, contract_type={case.contract_type}")
    return case


async def extract_risk_patterns(
    db: AsyncSession,
    contract_type: str,
    opinions: List[dict],
) -> List[RiskPattern]:
    """从审查意见中提取风险模式"""
    patterns = []
    
    for opinion in opinions:
        category = opinion.get("category", "other")
        risk_level = opinion.get("risk_level", "medium")
        title = opinion.get("title", "")
        description = opinion.get("description", "")
        
        # 检查是否已存在类似模式
        result = await db.execute(
            select(RiskPattern)
            .where(RiskPattern.pattern_type == category)
            .where(RiskPattern.contract_types.contains(contract_type))
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # 增加频次
            existing.frequency += 1
            existing.last_seen = datetime.utcnow()
            # 更新严重程度（取更高）
            severity_order = {"low": 1, "medium": 2, "high": 3}
            if severity_order.get(risk_level, 0) > severity_order.get(existing.severity.value, 0):
                existing.severity = risk_level
            patterns.append(existing)
        else:
            # 创建新模式
            pattern = RiskPattern(
                pattern_name=title[:100],
                pattern_type=category,
                description=description[:500],
                severity=risk_level,
                contract_types=contract_type,
                frequency=1,
                recommendation=opinion.get("suggestion", "")[:500],
                legal_basis=opinion.get("legal_basis", "")[:500],
            )
            db.add(pattern)
            patterns.append(pattern)
    
    await db.commit()
    return patterns


async def get_similar_cases(
    db: AsyncSession,
    contract_type: str,
    limit: int = 5,
) -> List[ReviewCase]:
    """获取同类型的历史审查案例"""
    result = await db.execute(
        select(ReviewCase)
        .where(ReviewCase.contract_type == contract_type)
        .order_by(ReviewCase.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def get_risk_patterns_for_type(
    db: AsyncSession,
    contract_type: str,
) -> List[RiskPattern]:
    """获取合同类型的风险模式"""
    result = await db.execute(
        select(RiskPattern)
        .where(RiskPattern.contract_types.contains(contract_type))
        .order_by(RiskPattern.frequency.desc())
    )
    return result.scalars().all()


async def save_contract_knowledge(
    db: AsyncSession,
    contract_type: str,
    knowledge_type: str,
    title: str,
    content: str,
    source: str = "manual",
    created_by: Optional[int] = None,
) -> ContractKnowledge:
    """保存合同领域知识"""
    knowledge = ContractKnowledge(
        contract_type=contract_type,
        knowledge_type=knowledge_type,
        title=title[:200],
        content=content,
        source=source,
        created_by=created_by,
    )
    db.add(knowledge)
    await db.commit()
    await db.refresh(knowledge)
    return knowledge


async def search_knowledge(
    db: AsyncSession,
    contract_type: str,
    keyword: Optional[str] = None,
    knowledge_type: Optional[str] = None,
    limit: int = 10,
) -> List[ContractKnowledge]:
    """搜索领域知识"""
    query = select(ContractKnowledge).where(
        ContractKnowledge.contract_type == contract_type
    )
    
    if knowledge_type:
        query = query.where(ContractKnowledge.knowledge_type == knowledge_type)
    
    if keyword:
        query = query.where(
            (ContractKnowledge.title.contains(keyword)) |
            (ContractKnowledge.content.contains(keyword))
        )
    
    query = query.order_by(ContractKnowledge.usefulness_score.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
