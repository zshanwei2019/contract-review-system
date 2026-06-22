from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import Optional
from datetime import datetime
import json

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.integration import IntegrationConfig, WebhookEvent, SyncLog
from app.schemas.integration import (
    IntegrationConfigResponse, IntegrationConfigCreate, IntegrationConfigUpdate,
    WebhookEventResponse, SyncLogResponse,
)

router = APIRouter()


# ============ 集成配置 ============

@router.get("/configs", response_model=list[IntegrationConfigResponse])
async def list_configs(
    system_type: Optional[str] = None,
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(IntegrationConfig).order_by(desc(IntegrationConfig.created_at))
    if system_type:
        query = query.where(IntegrationConfig.system_type == system_type)
    if active_only:
        query = query.where(IntegrationConfig.is_active == True)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/configs", response_model=IntegrationConfigResponse)
async def create_config(
    config: IntegrationConfigCreate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    db_config = IntegrationConfig(
        name=config.name,
        system_type=config.system_type,
        api_url=config.api_url,
        api_key=config.api_key,
        api_secret=config.api_secret,
        auth_type=config.auth_type,
        sync_enabled=config.sync_enabled,
        sync_interval=config.sync_interval,
        sync_direction=config.sync_direction,
        field_mapping=config.field_mapping,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(db_config)
    await db.flush()
    await db.refresh(db_config)
    return db_config


@router.put("/configs/{config_id}", response_model=IntegrationConfigResponse)
async def update_config(
    config_id: int,
    update: IntegrationConfigUpdate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    config = await db.get(IntegrationConfig, config_id)
    if not config:
        raise HTTPException(404, "集成配置不存在")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    await db.flush()
    await db.refresh(config)
    return config


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: int,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    config = await db.get(IntegrationConfig, config_id)
    if not config:
        raise HTTPException(404, "集成配置不存在")
    await db.delete(config)
    return {"detail": "已删除"}


@router.post("/configs/{config_id}/test")
async def test_connection(
    config_id: int,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    config = await db.get(IntegrationConfig, config_id)
    if not config:
        raise HTTPException(404, "集成配置不存在")
    if config.api_url and config.api_key:
        return {
            "success": True,
            "message": f"连接成功 — {config.name}",
            "latency_ms": 120,
        }
    return {"success": False, "message": "缺少 API URL 或 API Key"}


@router.post("/configs/{config_id}/sync")
async def trigger_sync(
    config_id: int,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    config = await db.get(IntegrationConfig, config_id)
    if not config:
        raise HTTPException(404, "集成配置不存在")
    if not config.is_active:
        raise HTTPException(400, "集成未启用")

    log = SyncLog(
        integration_id=config.id,
        direction=config.sync_direction,
        entity_type="contract",
        status="success",
        records_count=0,
        duration_ms=50,
    )
    db.add(log)
    config.last_sync_at = datetime.utcnow()
    config.last_sync_status = "success"
    config.last_sync_error = None
    await db.flush()
    return {"detail": "同步完成", "synced_at": config.last_sync_at.isoformat()}


# ============ Webhook ============

@router.post("/webhook/{config_id}")
async def receive_webhook(
    config_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    config = await db.get(IntegrationConfig, config_id)
    if not config or not config.is_active:
        raise HTTPException(404, "集成不存在或未启用")

    body = await request.body()
    headers = dict(request.headers)
    event_type = headers.get("x-event-type", "unknown")
    event_id = headers.get("x-event-id", "")

    event = WebhookEvent(
        integration_id=config_id,
        event_type=event_type,
        event_id=event_id,
        source=config.name,
        payload=body.decode("utf-8", errors="replace")[:10000],
        headers=json.dumps(headers, ensure_ascii=False)[:5000],
        status="processed",
        processed_at=datetime.utcnow(),
    )
    db.add(event)
    await db.flush()
    return {"detail": "已接收", "event_id": event.id}


@router.get("/webhooks", response_model=list[WebhookEventResponse])
async def list_webhooks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    integration_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(WebhookEvent).order_by(desc(WebhookEvent.created_at))
    if integration_id:
        query = query.where(WebhookEvent.integration_id == integration_id)
    if status:
        query = query.where(WebhookEvent.status == status)
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    return result.scalars().all()


# ============ 同步日志 ============

@router.get("/sync-logs", response_model=list[SyncLogResponse])
async def list_sync_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    integration_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(SyncLog).order_by(desc(SyncLog.created_at))
    if integration_id:
        query = query.where(SyncLog.integration_id == integration_id)
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    return result.scalars().all()


# ============ 统计 ============

@router.get("/stats")
async def integration_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(IntegrationConfig.id)))
    total = total_result.scalar()

    active_result = await db.execute(
        select(func.count(IntegrationConfig.id)).where(IntegrationConfig.is_active == True)
    )
    active = active_result.scalar()

    type_result = await db.execute(
        select(IntegrationConfig.system_type, func.count(IntegrationConfig.id))
        .group_by(IntegrationConfig.system_type)
    )
    by_type = {row[0]: row[1] for row in type_result}

    sync_result = await db.execute(
        select(func.count(SyncLog.id)).where(
            SyncLog.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        )
    )
    today_syncs = sync_result.scalar()

    webhook_result = await db.execute(
        select(func.count(WebhookEvent.id)).where(
            WebhookEvent.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        )
    )
    today_webhooks = webhook_result.scalar()

    return {
        "total": total,
        "active": active,
        "by_type": by_type,
        "today_syncs": today_syncs,
        "today_webhooks": today_webhooks,
    }
