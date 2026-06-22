from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON
from datetime import datetime

from app.core.database import Base


class SignatureRequest(Base):
    """电子签章请求"""
    __tablename__ = "signature_requests"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)

    # 签署方信息
    signer_name = Column(String(100), nullable=False)
    signer_email = Column(String(200))
    signer_phone = Column(String(20))
    signer_id_number = Column(String(50))  # 身份证号

    # 签章信息
    signature_type = Column(String(20), default="enterprise")  # enterprise, personal
    position = Column(String(200))  # 签章位置描述
    seal_image_url = Column(String(500))  # 印章图片URL

    # 状态
    status = Column(String(20), default="pending")  # pending, signed, rejected, expired, revoked
    signed_at = Column(DateTime)
    expires_at = Column(DateTime)

    # 证书信息
    certificate_sn = Column(String(200))  # 证书序列号
    certificate_issuer = Column(String(200))  # 证书颁发机构
    hash_value = Column(String(500))  # 签章哈希值

    # 审计
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 备注
    remark = Column(Text)


class Seal(Base):
    """印章管理"""
    __tablename__ = "seals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # 印章名称
    seal_type = Column(String(20), nullable=False)  # official, contract, finance, legal
    image_url = Column(String(500), nullable=False)  # 印章图片

    # 授权
    owner_id = Column(Integer, ForeignKey("users.id"))
    authorized_users = Column(JSON)  # 授权使用人ID列表

    # 状态
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 数字证书
    certificate_sn = Column(String(200))
    certificate_expiry = Column(DateTime)


class SignatureLog(Base):
    """签章操作日志"""
    __tablename__ = "signature_logs"

    id = Column(Integer, primary_key=True, index=True)
    signature_request_id = Column(Integer, ForeignKey("signature_requests.id"), nullable=False)
    action = Column(String(50), nullable=False)  # create, sign, reject, revoke, verify
    operator = Column(String(50))
    detail = Column(Text)
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
