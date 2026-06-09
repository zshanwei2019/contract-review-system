from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from datetime import datetime

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String(50))
    
    # 操作信息
    action = Column(String(50), nullable=False)  # create, update, delete, login, logout, etc.
    resource_type = Column(String(50))  # contract, review, user, etc.
    resource_id = Column(Integer)
    resource_name = Column(String(200))
    
    # 详情
    detail = Column(Text)  # JSON格式详情
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    
    # 结果
    status = Column(String(20))  # success, failure
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class OperationLog(Base):
    __tablename__ = "operation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String(50))
    
    # 操作信息
    module = Column(String(50))  # 模块
    action = Column(String(50))  # 操作
    method = Column(String(10))  # HTTP方法
    path = Column(String(500))  # 请求路径
    
    # 请求详情
    request_body = Column(Text)
    response_code = Column(Integer)
    response_body = Column(Text)
    
    # 性能
    duration = Column(Integer)  # 耗时(ms)
    
    # 客户端信息
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
