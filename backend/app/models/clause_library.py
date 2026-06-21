from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class ClauseCategory(str, enum.Enum):
    PAYMENT = "payment"          # 付款条款
    LIABILITY = "liability"      # 违约责任
    CONFIDENTIALITY = "confidentiality"  # 保密条款
    INTELLECTUAL = "intellectual"  # 知识产权
    TERMINATION = "termination"    # 终止条款
    DISPUTE = "dispute"           # 争议解决
    WARRANTY = "warranty"         # 质保条款
    DELIVERY = "delivery"         # 交付条款
    FORCE_MAJEURE = "force_majeure"  # 不可抗力
    OTHER = "other"               # 其他


class ClauseLibrary(Base):
    __tablename__ = "clause_library"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    contract_type = Column(String(50), nullable=True, index=True)  # 适用合同类型, null=通用
    risk_level = Column(String(20), default="low")  # low/medium/high
    tags = Column(String(500))  # 逗号分隔标签
    source = Column(String(20), default="standard")  # standard/custom
    usage_count = Column(Integer, default=0)  # 使用次数

    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClauseFavorite(Base):
    __tablename__ = "clause_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    clause_id = Column(Integer, ForeignKey("clause_library.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
