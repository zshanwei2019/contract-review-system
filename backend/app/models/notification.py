from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class NotificationType(str, enum.Enum):
    SYSTEM = "system"  # 系统通知
    REVIEW = "review"  # 审查通知
    APPROVAL = "approval"  # 审批通知
    DEADLINE = "deadline"  # 到期提醒
    RISK = "risk"  # 风险提醒


class NotificationStatus(str, enum.Enum):
    UNREAD = "unread"  # 未读
    READ = "read"  # 已读
    ARCHIVED = "archived"  # 已归档


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 通知内容
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    
    # 关联
    resource_type = Column(String(50))  # contract, review, workflow
    resource_id = Column(Integer)
    
    # 状态
    status = Column(Enum(NotificationStatus), default=NotificationStatus.UNREAD)
    is_pushed = Column(Boolean, default=False)  # 是否已推送
    
    # 发送渠道
    channel = Column(String(20))  # web, email, sms, wechat
    
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="notifications")


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    type = Column(Enum(NotificationType), nullable=False)
    
    # 模板内容
    title_template = Column(String(200), nullable=False)
    content_template = Column(Text, nullable=False)
    
    # 配置
    channels = Column(String(100))  # 支持的渠道，逗号分隔
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
