from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class WorkflowStatus(str, enum.Enum):
    ACTIVE = "active"  # 启用
    INACTIVE = "inactive"  # 停用
    DRAFT = "draft"  # 草稿


class InstanceStatus(str, enum.Enum):
    RUNNING = "running"  # 运行中
    COMPLETED = "completed"  # 已完成
    REJECTED = "rejected"  # 已驳回
    CANCELLED = "cancelled"  # 已取消
    SUSPENDED = "suspended"  # 已挂起


class StepType(str, enum.Enum):
    START = "start"  # 开始
    REVIEW = "review"  # 审查
    APPROVAL = "approval"  # 审批
    CC = "cc"  # 抄送
    CONDITION = "condition"  # 条件判断
    END = "end"  # 结束


class StepStatus(str, enum.Enum):
    PENDING = "pending"  # 待处理
    APPROVED = "approved"  # 已通过
    REJECTED = "rejected"  # 已驳回
    SKIPPED = "skipped"  # 已跳过


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    contract_type = Column(String(50))
    
    # 流程定义
    steps_definition = Column(Text)  # JSON格式步骤定义
    conditions = Column(Text)  # JSON格式条件
    
    status = Column(Enum(WorkflowStatus), default=WorkflowStatus.ACTIVE)
    version = Column(Integer, default=1)
    
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    instances = relationship("WorkflowInstance", back_populates="workflow")


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflow_definitions.id"), nullable=False)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    
    status = Column(Enum(InstanceStatus), default=InstanceStatus.RUNNING, index=True)
    current_step = Column(Integer)  # 当前步骤序号
    
    # 发起人
    initiator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 时间
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    workflow = relationship("WorkflowDefinition", back_populates="instances")
    steps = relationship("WorkflowStep", back_populates="instance")


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    
    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, ForeignKey("workflow_instances.id"), nullable=False)
    
    step_no = Column(Integer, nullable=False)  # 步骤序号
    step_type = Column(Enum(StepType), nullable=False)
    name = Column(String(100), nullable=False)
    
    # 处理人
    assignee_id = Column(Integer, ForeignKey("users.id"))
    assignee_type = Column(String(20))  # user, role, department
    
    # 状态
    status = Column(Enum(StepStatus), default=StepStatus.PENDING)
    result = Column(String(50))  # approved, rejected
    remark = Column(Text)  # 备注
    
    # 时间
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    deadline = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    instance = relationship("WorkflowInstance", back_populates="steps")
