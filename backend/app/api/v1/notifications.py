from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.notification import Notification, NotificationStatus, NotificationType
from app.schemas.notification import (
    NotificationResponse, NotificationList, NotificationCount,
)

router = APIRouter()


@router.get("", response_model=NotificationList)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[NotificationStatus] = None,
    notification_type: Optional[NotificationType] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取通知列表"""
    query = select(Notification).where(Notification.user_id == current_user.id)
    count_query = select(func.count()).select_from(Notification).where(Notification.user_id == current_user.id)
    
    if status:
        query = query.where(Notification.status == status)
        count_query = count_query.where(Notification.status == status)
    
    if notification_type:
        query = query.where(Notification.type == notification_type)
        count_query = count_query.where(Notification.type == notification_type)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get unread count
    unread_result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id)
        .where(Notification.status == NotificationStatus.UNREAD)
    )
    unread_count = unread_result.scalar()
    
    # Get paginated results
    query = query.order_by(Notification.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return NotificationList(
        total=total,
        unread_count=unread_count,
        items=notifications,
    )


@router.get("/count", response_model=NotificationCount)
async def get_notification_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取通知统计"""
    total_result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id)
    )
    total = total_result.scalar()
    
    unread_result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id)
        .where(Notification.status == NotificationStatus.UNREAD)
    )
    unread = unread_result.scalar()
    
    return NotificationCount(total=total, unread=unread)


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记通知已读"""
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == current_user.id)
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在",
        )
    
    notification.status = NotificationStatus.READ
    notification.read_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "已标记为已读"}


@router.put("/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记所有通知已读"""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .where(Notification.status == NotificationStatus.UNREAD)
        .values(
            status=NotificationStatus.READ,
            read_at=datetime.utcnow(),
        )
    )
    await db.commit()
    
    return {"message": "已全部标记为已读"}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除通知"""
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == current_user.id)
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在",
        )
    
    await db.delete(notification)
    await db.commit()
