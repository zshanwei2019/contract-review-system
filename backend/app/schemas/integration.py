from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class IntegrationConfigResponse(BaseModel):
    id: int
    name: str
    system_type: str
    api_url: Optional[str] = None
    auth_type: str
    sync_enabled: bool
    sync_interval: int
    sync_direction: str
    is_active: bool
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_error: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


class IntegrationConfigCreate(BaseModel):
    name: str
    system_type: str
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    auth_type: str = "bearer"
    sync_enabled: bool = False
    sync_interval: int = 300
    sync_direction: str = "bidirectional"
    field_mapping: Optional[dict] = None


class IntegrationConfigUpdate(BaseModel):
    name: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    auth_type: Optional[str] = None
    sync_enabled: Optional[bool] = None
    sync_interval: Optional[int] = None
    sync_direction: Optional[str] = None
    is_active: Optional[bool] = None
    field_mapping: Optional[dict] = None


class WebhookEventResponse(BaseModel):
    id: int
    integration_id: Optional[int] = None
    event_type: str
    event_id: Optional[str] = None
    source: Optional[str] = None
    status: str
    retry_count: int
    created_at: datetime
    class Config:
        from_attributes = True


class SyncLogResponse(BaseModel):
    id: int
    integration_id: int
    direction: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    status: str
    records_count: int
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime
    class Config:
        from_attributes = True
