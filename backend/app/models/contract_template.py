from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from datetime import datetime
import enum

from app.core.database import Base


class TemplateStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContractTemplate(Base):
    __tablename__ = "contract_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    contract_type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)  # 模板正文(含变量占位符 {{var}})
    clauses = Column(Text)  # JSON: 关联条款ID列表
    variables = Column(Text)  # JSON: [{"name":"party_a","label":"甲方名称","required":true}]
    status = Column(Enum(TemplateStatus), default=TemplateStatus.DRAFT)
    version = Column(Integer, default=1)
    usage_count = Column(Integer, default=0)

    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
