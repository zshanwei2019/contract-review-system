"""
主动监控服务 - 合同到期提醒 + 法规变更提醒
"""

import json
import logging
from typing import Optional, List
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.contract import Contract, ContractStatus
from app.models.user import User
from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def check_expiring_contracts(db: AsyncSession) -> List[dict]:
    """检查即将到期的合同"""
    now = datetime.utcnow()
    
    # 30天内到期
    warning_date = now + timedelta(days=30)
    # 7天内到期
    urgent_date = now + timedelta(days=7)
    
    # 查询即将到期的合同
    result = await db.execute(
        select(Contract)
        .where(
            and_(
                Contract.expiry_date.isnot(None),
                Contract.expiry_date <= warning_date,
                Contract.expiry_date > now,
                Contract.status.in_([
                    ContractStatus.APPROVED,
                    ContractStatus.REVIEWED,
                ])
            )
        )
        .order_by(Contract.expiry_date)
    )
    contracts = result.scalars().all()
    
    alerts = []
    for contract in contracts:
        days_left = (contract.expiry_date - now).days
        urgency = "urgent" if days_left <= 7 else "warning"
        
        alerts.append({
            "contract_id": contract.id,
            "contract_no": contract.contract_no,
            "title": contract.title,
            "expiry_date": contract.expiry_date.isoformat(),
            "days_left": days_left,
            "urgency": urgency,
            "message": f"合同「{contract.title}」将在{days_left}天后到期（{contract.expiry_date.strftime('%Y-%m-%d')}），请及时处理续约或终止事宜。",
        })
    
    return alerts


async def check_overdue_contracts(db: AsyncSession) -> List[dict]:
    """检查已过期未处理的合同"""
    now = datetime.utcnow()
    
    result = await db.execute(
        select(Contract)
        .where(
            and_(
                Contract.expiry_date.isnot(None),
                Contract.expiry_date < now,
                Contract.status.in_([
                    ContractStatus.APPROVED,
                    ContractStatus.REVIEWED,
                ])
            )
        )
    )
    contracts = result.scalars().all()
    
    alerts = []
    for contract in contracts:
        days_overdue = (now - contract.expiry_date).days
        alerts.append({
            "contract_id": contract.id,
            "contract_no": contract.contract_no,
            "title": contract.title,
            "expiry_date": contract.expiry_date.isoformat(),
            "days_overdue": days_overdue,
            "urgency": "overdue",
            "message": f"⚠️ 合同「{contract.title}」已过期{days_overdue}天，请立即处理。",
        })
    
    return alerts


async def check_pending_reviews(db: AsyncSession) -> List[dict]:
    """检查待审查的合同"""
    result = await db.execute(
        select(Contract)
        .where(Contract.status == ContractStatus.PENDING_REVIEW)
        .order_by(Contract.created_at)
    )
    contracts = result.scalars().all()
    
    alerts = []
    for contract in contracts:
        days_waiting = (datetime.utcnow() - contract.created_at).days
        if days_waiting > 3:  # 超过3天未审查
            alerts.append({
                "contract_id": contract.id,
                "contract_no": contract.contract_no,
                "title": contract.title,
                "days_waiting": days_waiting,
                "urgency": "warning",
                "message": f"合同「{contract.title}」已等待审查{days_waiting}天，请安排审查。",
            })
    
    return alerts


async def generate_monitoring_alerts(db: AsyncSession) -> dict:
    """生成监控报告"""
    expiring = await check_expiring_contracts(db)
    overdue = await check_overdue_contracts(db)
    pending = await check_pending_reviews(db)
    
    total_alerts = len(expiring) + len(overdue) + len(pending)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_alerts": total_alerts,
        "expiring_contracts": {
            "count": len(expiring),
            "items": expiring,
        },
        "overdue_contracts": {
            "count": len(overdue),
            "items": overdue,
        },
        "pending_reviews": {
            "count": len(pending),
            "items": pending,
        },
        "summary": _generate_summary(expiring, overdue, pending),
    }


def _generate_summary(expiring, overdue, pending) -> str:
    """生成监控摘要"""
    parts = []
    if overdue:
        parts.append(f"🔴 {len(overdue)}份合同已过期")
    if expiring:
        parts.append(f"🟡 {len(expiring)}份合同即将到期")
    if pending:
        parts.append(f"🔵 {len(pending)}份合同待审查")
    
    if not parts:
        return "✅ 当前无异常，一切正常。"
    return "监控报告：" + "，".join(parts)


async def send_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    content: str,
    notification_type: str = "system",
):
    """发送通知"""
    notification = Notification(
        user_id=user_id,
        title=title,
        content=content,
        type=notification_type,
        is_read=False,
    )
    db.add(notification)
    await db.commit()
