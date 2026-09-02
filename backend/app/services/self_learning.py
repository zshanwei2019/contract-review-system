"""
自学习循环服务
基于人工反馈优化审查策略
FP-Growth关联规则挖掘
"""

import json
import logging
from collections import Counter, defaultdict
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import ReviewCase, RiskPattern, CorrectionLog

logger = logging.getLogger(__name__)


async def learn_from_corrections(db: AsyncSession, limit: int = 100) -> Dict:
    """从人工纠正中学习"""
    # 获取最近的纠正记录
    result = await db.execute(
        select(CorrectionLog)
        .where(CorrectionLog.is_learned == False)
        .order_by(CorrectionLog.created_at.desc())
        .limit(limit)
    )
    corrections = result.scalars().all()

    if not corrections:
        return {"message": "没有新的纠正记录需要学习", "learned": 0}

    learned_count = 0
    pattern_updates = defaultdict(lambda: {"count": 0, "corrections": []})

    for correction in corrections:
        # 提取纠正中的风险模式
        original = correction.original_opinion or ""
        corrected = correction.corrected_opinion or ""

        if not corrected:
            continue

        # 分析纠正内容，提取模式
        patterns = _extract_patterns_from_correction(original, corrected)

        for pattern in patterns:
            pattern_key = pattern["keyword"]
            pattern_updates[pattern_key]["count"] += 1
            pattern_updates[pattern_key]["corrections"].append({
                "original": original[:200],
                "corrected": corrected[:200],
                "correction_type": correction.correction_type,
            })

        # 标记为已学习
        correction.is_learned = True
        learned_count += 1

    # 更新风险模式库
    patterns_created = 0
    for pattern_key, data in pattern_updates.items():
        if data["count"] >= 2:  # 至少2次相同模式才创建规则
            # 检查是否已存在
            existing = await db.execute(
                select(RiskPattern).where(RiskPattern.pattern_name == pattern_key)
            )
            existing_pattern = existing.scalar_one_or_none()

            if existing_pattern:
                # 更新频率
                existing_pattern.frequency = (existing_pattern.frequency or 0) + data["count"]
                existing_pattern.last_seen = datetime.utcnow()
            else:
                # 创建新模式
                new_pattern = RiskPattern(
                    pattern_name=pattern_key,
                    pattern_type="learned",
                    description=f"从{data['count']}次人工纠正中学习到的风险模式",
                    frequency=data["count"],
                    risk_level="medium",
                    examples=json.dumps(data["corrections"][:3], ensure_ascii=False),
                )
                db.add(new_pattern)
                patterns_created += 1

    await db.commit()

    return {
        "learned": learned_count,
        "patterns_updated": len(pattern_updates),
        "patterns_created": patterns_created,
    }


def _extract_patterns_from_correction(original: str, corrected: str) -> List[Dict]:
    """从纠正中提取模式"""
    patterns = []

    # 提取关键词差异
    risk_keywords = [
        "违约", "赔偿", "保密", "知识产权", "不可抗力", "争议",
        "付款", "交付", "验收", "质保", "担保", "保险",
    ]

    for kw in risk_keywords:
        if kw in corrected and kw not in original:
            patterns.append({"keyword": kw, "type": "missing_keyword"})
        elif kw in original and kw in corrected:
            # 关键词都在，但表述不同
            patterns.append({"keyword": kw, "type": "refined"})

    return patterns


async def get_learning_stats(db: AsyncSession) -> Dict:
    """获取学习统计"""
    # 总纠正数
    total_corrections = await db.execute(
        select(func.count(CorrectionLog.id))
    )
    total = total_corrections.scalar() or 0

    # 已学习数
    learned = await db.execute(
        select(func.count(CorrectionLog.id)).where(CorrectionLog.is_learned == True)
    )
    learned_count = learned.scalar() or 0

    # 风险模式数
    patterns = await db.execute(select(func.count(RiskPattern.id)))
    pattern_count = patterns.scalar() or 0

    # 按类型统计
    type_stats = await db.execute(
        select(CorrectionLog.correction_type, func.count(CorrectionLog.id))
        .group_by(CorrectionLog.correction_type)
    )
    by_type = {row[0]: row[1] for row in type_stats.all() if row[0]}

    return {
        "total_corrections": total,
        "learned_corrections": learned_count,
        "unlearned_corrections": total - learned_count,
        "total_patterns": pattern_count,
        "corrections_by_type": by_type,
        "learning_rate": round(learned_count / total * 100, 1) if total > 0 else 0,
    }


async def run_fp_growth(db: AsyncSession, min_support: int = 2) -> List[Dict]:
    """
    FP-Growth关联规则挖掘
    发现审查发现之间的关联关系
    """
    # 获取最近的审查案例
    result = await db.execute(
        select(ReviewCase)
        .where(ReviewCase.created_at >= datetime.utcnow() - timedelta(days=90))
        .order_by(ReviewCase.created_at.desc())
        .limit(500)
    )
    cases = result.scalars().all()

    if len(cases) < 5:
        return []

    # 提取每个案例的风险标签
    transactions = []
    for case in cases:
        tags = []
        if case.findings:
            try:
                findings = json.loads(case.findings) if isinstance(case.findings, str) else case.findings
                for f in findings:
                    tags.append(f.get("category", "unknown"))
            except (json.JSONDecodeError, TypeError):
                pass

        if case.risk_level:
            tags.append(f"risk_{case.risk_level}")

        if tags:
            transactions.append(set(tags))

    # 简化版FP-Growth：计算项集支持度
    item_counts = Counter()
    pair_counts = Counter()

    for transaction in transactions:
        for item in transaction:
            item_counts[item] += 1
        # 计算两两组合
        items = sorted(transaction)
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                pair_counts[(items[i], items[j])] += 1

    # 过滤低支持度
    frequent_pairs = [
        {
            "itemset": list(pair),
            "support": count,
            "confidence": round(count / item_counts[pair[0]], 2) if item_counts[pair[0]] > 0 else 0,
        }
        for pair, count in pair_counts.items()
        if count >= min_support
    ]

    frequent_pairs.sort(key=lambda x: x["support"], reverse=True)
    return frequent_pairs[:20]
