from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.audit import AuditLog, OperationLog
from app.schemas.audit import AuditLogResponse, OperationLogResponse

router = APIRouter()


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """获取审计日志"""
    query = select(AuditLog).order_by(desc(AuditLog.created_at))
    
    if username:
        query = query.where(AuditLog.username.ilike(f"%{username}%"))
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if status:
        query = query.where(AuditLog.status == status)
    if start_date:
        query = query.where(AuditLog.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(AuditLog.created_at <= datetime.fromisoformat(end_date))
    
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/audit-logs/count")
async def count_audit_logs(
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """审计日志总数"""
    query = select(func.count(AuditLog.id))
    if username:
        query = query.where(AuditLog.username.ilike(f"%{username}%"))
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if status:
        query = query.where(AuditLog.status == status)
    if start_date:
        query = query.where(AuditLog.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(AuditLog.created_at <= datetime.fromisoformat(end_date))
    result = await db.execute(query)
    return {"total": result.scalar()}


@router.get("/operation-logs", response_model=list[OperationLogResponse])
async def list_operation_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    username: Optional[str] = None,
    module: Optional[str] = None,
    method: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """获取操作日志"""
    query = select(OperationLog).order_by(desc(OperationLog.created_at))
    
    if username:
        query = query.where(OperationLog.username.ilike(f"%{username}%"))
    if module:
        query = query.where(OperationLog.module == module)
    if method:
        query = query.where(OperationLog.method == method)
    if start_date:
        query = query.where(OperationLog.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(OperationLog.created_at <= datetime.fromisoformat(end_date))
    
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats")
async def audit_stats(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """审计统计概览"""
    since = datetime.utcnow() - timedelta(days=days)
    
    # 按操作类型统计
    action_result = await db.execute(
        select(AuditLog.action, func.count(AuditLog.id))
        .where(AuditLog.created_at >= since)
        .group_by(AuditLog.action)
    )
    by_action = {row[0]: row[1] for row in action_result}
    
    # 按资源类型统计
    resource_result = await db.execute(
        select(AuditLog.resource_type, func.count(AuditLog.id))
        .where(AuditLog.created_at >= since)
        .group_by(AuditLog.resource_type)
    )
    by_resource = {row[0]: row[1] for row in resource_result}
    
    # 按用户统计
    user_result = await db.execute(
        select(AuditLog.username, func.count(AuditLog.id))
        .where(AuditLog.created_at >= since)
        .group_by(AuditLog.username)
    )
    by_user = {row[0]: row[1] for row in user_result}
    
    # 成功/失败统计
    status_result = await db.execute(
        select(AuditLog.status, func.count(AuditLog.id))
        .where(AuditLog.created_at >= since)
        .group_by(AuditLog.status)
    )
    by_status = {row[0]: row[1] for row in status_result}
    
    return {
        "days": days,
        "total": sum(by_action.values()),
        "by_action": by_action,
        "by_resource": by_resource,
        "by_user": by_user,
        "by_status": by_status,
    }
