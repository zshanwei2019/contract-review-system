from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class ReviewTaskStatus(str, enum.Enum):
    PENDING = "pending"  # 待处理
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"  # 已完成
    RETURNED = "returned"  # 已退回
    CANCELLED = "cancelled"  # 已取消


class ReviewResult(str, enum.Enum):
    APPROVED = "approved"  # 通过
    REJECTED = "rejected"  # 驳回
    NEED_REVISION = "need_revision"  # 需修改
    CONDITIONAL = "conditional"  # 有条件通过


class ReviewTask(Base):
    __tablename__ = "review_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"))
    
    status = Column(Enum(ReviewTaskStatus), default=ReviewTaskStatus.PENDING, index=True)
    result = Column(Enum(ReviewResult))
    
    # 审查内容
    review_opinion = Column(Text)  # 审查意见
    risk_level = Column(String(20))  # 风险等级
    risk_score = Column(Integer)  # 风险评分
    summary = Column(Text)  # 审查摘要
    
    # 时间
    deadline = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contract = relationship("Contract", back_populates="review_tasks")
    reviewer = relationship("User", back_populates="review_tasks", foreign_keys=[reviewer_id])
    assigned_by_user = relationship("User", foreign_keys=[assigned_by])
    opinions = relationship("ReviewOpinion", back_populates="review_task")


class ReviewOpinion(Base):
    __tablename__ = "review_opinions"
    
    id = Column(Integer, primary_key=True, index=True)
    review_task_id = Column(Integer, ForeignKey("review_tasks.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 意见内容
    opinion_type = Column(String(50))  # legal, business, risk, compliance
    content = Column(Text, nullable=False)
    suggestion = Column(Text)  # 修改建议
    risk_level = Column(String(20))  # high, medium, low
    
    # 引用
    clause_reference = Column(String(200))  # 条款引用
    legal_basis = Column(String(500))  # 法律依据
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    review_task = relationship("ReviewTask", back_populates="opinions")


class ReviewTemplate(Base):
    __tablename__ = "review_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    contract_type = Column(String(50))
    description = Column(Text)
    
    # 审查要点
    checklist = Column(Text)  # JSON格式审查清单
    risk_rules = Column(Text)  # JSON格式风险规则
    
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
