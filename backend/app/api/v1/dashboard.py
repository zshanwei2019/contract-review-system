from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, and_
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.contract import Contract, ContractStatus, ContractType
from app.models.review import ReviewTask, ReviewTaskStatus
from app.models.risk import RiskItem, RiskLevel
from app.models.notification import Notification, NotificationStatus

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """获取仪表盘统计数据"""
    
    # Contract stats
    total_contracts_result = await db.execute(
        select(func.count()).select_from(Contract)
    )
    total_contracts = total_contracts_result.scalar()
    
    # Status distribution
    status_dist_result = await db.execute(
        select(
            Contract.status,
            func.count().label("count"),
        )
        .group_by(Contract.status)
    )
    status_distribution = {row.status: row.count for row in status_dist_result}
    
    # Type distribution
    type_dist_result = await db.execute(
        select(
            Contract.contract_type,
            func.count().label("count"),
        )
        .group_by(Contract.contract_type)
    )
    type_distribution = {row.contract_type: row.count for row in type_dist_result}
    
    # Risk distribution
    risk_dist_result = await db.execute(
        select(
            RiskItem.risk_level,
            func.count().label("count"),
        )
        .group_by(RiskItem.risk_level)
    )
    risk_distribution = {row.risk_level: row.count for row in risk_dist_result}
    
    # Review stats
    pending_reviews_result = await db.execute(
        select(func.count())
        .select_from(ReviewTask)
        .where(ReviewTask.status == ReviewTaskStatus.PENDING)
    )
    pending_reviews = pending_reviews_result.scalar()
    
    in_progress_reviews_result = await db.execute(
        select(func.count())
        .select_from(ReviewTask)
        .where(ReviewTask.status == ReviewTaskStatus.IN_PROGRESS)
    )
    in_progress_reviews = in_progress_reviews_result.scalar()
    
    # Recent contracts
    recent_contracts_result = await db.execute(
        select(Contract)
        .order_by(Contract.created_at.desc())
        .limit(10)
    )
    recent_contracts = recent_contracts_result.scalars().all()
    
    # Unread notifications
    unread_notifications_result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id)
        .where(Notification.status == NotificationStatus.UNREAD)
    )
    unread_notifications = unread_notifications_result.scalar()
    
    # Monthly trend (last 6 months)
    monthly_trend = []
    for i in range(5, -1, -1):
        month_start = datetime.now().replace(day=1) - timedelta(days=30 * i)
        month_end = month_start + timedelta(days=30)
        
        month_count_result = await db.execute(
            select(func.count())
            .select_from(Contract)
            .where(Contract.created_at >= month_start)
            .where(Contract.created_at < month_end)
        )
        month_count = month_count_result.scalar()
        
        monthly_trend.append({
            "month": month_start.strftime("%Y-%m"),
            "count": month_count,
        })
    
    return {
        "total_contracts": total_contracts,
        "status_distribution": status_distribution,
        "type_distribution": type_distribution,
        "risk_distribution": risk_distribution,
        "pending_reviews": pending_reviews,
        "in_progress_reviews": in_progress_reviews,
        "unread_notifications": unread_notifications,
        "recent_contracts": [
            {
                "id": c.id,
                "title": c.title,
                "contract_type": c.contract_type,
                "status": c.status,
                "risk_level": c.risk_level,
                "created_at": c.created_at.isoformat(),
            }
            for c in recent_contracts
        ],
        "monthly_trend": monthly_trend,
    }


@router.get("/my-tasks")
async def get_my_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """获取我的任务统计"""
    
    # Pending reviews
    pending_reviews_result = await db.execute(
        select(func.count())
        .select_from(ReviewTask)
        .where(ReviewTask.reviewer_id == current_user.id)
        .where(ReviewTask.status == ReviewTaskStatus.PENDING)
    )
    pending_reviews = pending_reviews_result.scalar()
    
    # In progress reviews
    in_progress_reviews_result = await db.execute(
        select(func.count())
        .select_from(ReviewTask)
        .where(ReviewTask.reviewer_id == current_user.id)
        .where(ReviewTask.status == ReviewTaskStatus.IN_PROGRESS)
    )
    in_progress_reviews = in_progress_reviews_result.scalar()
    
    # Completed reviews (this month)
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    completed_reviews_result = await db.execute(
        select(func.count())
        .select_from(ReviewTask)
        .where(ReviewTask.reviewer_id == current_user.id)
        .where(ReviewTask.status == ReviewTaskStatus.COMPLETED)
        .where(ReviewTask.completed_at >= month_start)
    )
    completed_reviews = completed_reviews_result.scalar()
    
    # My contracts
    my_contracts_result = await db.execute(
        select(func.count())
        .select_from(Contract)
        .where(Contract.uploader_id == current_user.id)
    )
    my_contracts = my_contracts_result.scalar()
    
    return {
        "pending_reviews": pending_reviews,
        "in_progress_reviews": in_progress_reviews,
        "completed_reviews": completed_reviews,
        "my_contracts": my_contracts,
    }
