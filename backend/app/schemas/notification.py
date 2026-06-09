from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models.notification import NotificationType, NotificationStatus


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: NotificationType
    title: str
    content: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    status: NotificationStatus
    channel: Optional[str] = None
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationList(BaseModel):
    total: int
    unread_count: int
    items: List[NotificationResponse]


class NotificationCount(BaseModel):
    total: int
    unread: int
