from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON
from datetime import datetime

from app.core.database import Base


class IntegrationConfig(Base):
    """外部系统集成配置"""
    __tablename__ = "integration_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # 集成名称
    system_type = Column(String(50), nullable=False)  # oa, erp, crm, sap, other

    # 连接配置
    api_url = Column(String(500))  # API地址
    api_key = Column(String(500))  # API Key
    api_secret = Column(String(500))  # API Secret
    auth_type = Column(String(20), default="bearer")  # bearer, basic, api_key, oauth2

    # 同步配置
    sync_enabled = Column(Boolean, default=False)
    sync_interval = Column(Integer, default=300)  # 同步间隔(秒)
    sync_direction = Column(String(20), default="bidirectional")  # inbound, outbound, bidirectional

    # 映射配置
    field_mapping = Column(JSON)  # 字段映射 {local_field: remote_field}

    # 状态
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    last_sync_status = Column(String(20))  # success, failure, partial
    last_sync_error = Column(Text)

    # 审计
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookEvent(Base):
    """Webhook 事件"""
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integration_configs.id"))

    # 事件信息
    event_type = Column(String(100), nullable=False)  # 事件类型
    event_id = Column(String(200))  # 外部事件ID
    source = Column(String(100))  # 来源系统

    # 数据
    payload = Column(Text)  # JSON payload
    headers = Column(Text)  # 请求头

    # 处理状态
    status = Column(String(20), default="pending")  # pending, processed, failed, ignored
    processed_at = Column(DateTime)
    result = Column(Text)  # 处理结果
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SyncLog(Base):
    """同步日志"""
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integration_configs.id"), nullable=False)

    # 同步信息
    direction = Column(String(20))  # inbound, outbound
    entity_type = Column(String(50))  # contract, user, department
    entity_id = Column(String(100))  # 实体ID

    # 结果
    status = Column(String(20), nullable=False)  # success, failure, skipped
    records_count = Column(Integer, default=0)
    error_message = Column(Text)

    duration_ms = Column(Integer)  # 耗时
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
