"""
反馈服务 - 人工修正AI意见 → 学习改进
"""

import json
import logging
from typing import Optional, List, Dict
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.memory import CorrectionLog, ReviewCase, RiskPattern
from app.models.review import ReviewOpinion

logger = logging.getLogger(__name__)


async def submit_correction(
    db: AsyncSession,
    review_case_id: int,
    corrector_id: int,
    original_opinion_id: Optional[int],
    corrected_opinion: str,
    correction_reason: str,
    correction_type: str = "modify",
) -> CorrectionLog:
    """提交人工修正"""
    # 获取原始意见
    original_text = ""
    if original_opinion_id:
        result = await db.execute(
            select(ReviewOpinion).where(ReviewOpinion.id == original_opinion_id)
        )
        opinion = result.scalar_one_or_none()
        if opinion:
            original_text = opinion.content

    correction = CorrectionLog(
        review_case_id=review_case_id,
        corrector_id=corrector_id,
        original_opinion=original_text,
        corrected_opinion=corrected_opinion,
        correction_reason=correction_reason,
        correction_type=correction_type,
    )
    db.add(correction)

    # 更新审查案例的评分
    result = await db.execute(
        select(ReviewCase).where(ReviewCase.id == review_case_id)
    )
    case = result.scalar_one_or_none()
    if case:
        # 附加到lessons_learned
        lessons = json.loads(case.lessons_learned) if case.lessons_learned else []
        lessons.append({
            "original": original_text[:200],
            "correction": corrected_opinion[:200],
            "reason": correction_reason[:200],
            "type": correction_type,
        })
        case.lessons_learned = json.dumps(lessons, ensure_ascii=False)

    await db.commit()
    await db.refresh(correction)

    logger.info(f"人工修正已提交: case_id={review_case_id}, type={correction_type}")
    return correction


async def rate_review_case(
    db: AsyncSession,
    case_id: int,
    user_id: int,
    rating: int,
    comment: Optional[str] = None,
) -> ReviewCase:
    """对审查案例评分"""
    result = await db.execute(
        select(ReviewCase).where(ReviewCase.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("审查案例不存在")

    case.human_rating = max(1, min(5, rating))
    case.human_comment = comment
    case.is_useful = rating >= 3

    await db.commit()
    await db.refresh(case)
    return case


async def get_pending_corrections(
    db: AsyncSession,
    limit: int = 20,
) -> List[CorrectionLog]:
    """获取待学习的修正记录"""
    result = await db.execute(
        select(CorrectionLog)
        .where(CorrectionLog.is_learned == False)
        .order_by(CorrectionLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def mark_correction_learned(
    db: AsyncSession,
    correction_id: int,
) -> CorrectionLog:
    """标记修正已学习"""
    result = await db.execute(
        select(CorrectionLog).where(CorrectionLog.id == correction_id)
    )
    correction = result.scalar_one_or_none()
    if not correction:
        raise ValueError("修正记录不存在")

    correction.is_learned = True
    correction.learned_at = datetime.utcnow()

    # 更新相关风险模式的建议
    await _update_risk_patterns_from_correction(db, correction)

    await db.commit()
    await db.refresh(correction)
    return correction


async def _update_risk_patterns_from_correction(
    db: AsyncSession,
    correction: CorrectionLog,
):
    """从修正中学习，更新风险模式"""
    # 获取案例信息
    result = await db.execute(
        select(ReviewCase).where(ReviewCase.id == correction.review_case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        return

    # 查找相关风险模式
    result = await db.execute(
        select(RiskPattern)
        .where(RiskPattern.contract_types.contains(case.contract_type))
        .where(RiskPattern.is_active == True)
    )
    patterns = result.scalars().all()

    for pattern in patterns:
        # 如果修正内容与模式相关，更新建议
        if pattern.recommendation and correction.correction_type == "modify":
            # 追加修正经验
            updated_rec = (
                pattern.recommendation
                + f"\n\n【人工修正经验】{correction.correction_reason}"
            )
            pattern.recommendation = updated_rec[:2000]
            logger.info(f"风险模式已更新: pattern_id={pattern.id}")


async def get_correction_stats(
    db: AsyncSession,
) -> dict:
    """获取修正统计"""
    from sqlalchemy import func

    total_result = await db.execute(
        select(func.count()).select_from(CorrectionLog)
    )
    total = total_result.scalar()

    learned_result = await db.execute(
        select(func.count())
        .select_from(CorrectionLog)
        .where(CorrectionLog.is_learned == True)
    )
    learned = learned_result.scalar()

    # 按修正类型分组
    type_result = await db.execute(
        select(CorrectionLog.correction_type, func.count())
        .group_by(CorrectionLog.correction_type)
    )
    by_type = dict(type_result.all())

    return {
        "total_corrections": total,
        "learned": learned,
        "pending": total - learned,
        "by_type": by_type,
    }
