from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Numeric, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class ContractType(str, enum.Enum):
    PROCUREMENT = "procurement"  # 采购合同
    SALES = "sales"  # 销售合同
    OUTSOURCING = "outsourcing"  # 外协/外包合同
    EQUIPMENT = "equipment"  # 设备合同
    LEASE = "lease"  # 租赁合同
    POWER_SUPPLY = "power_supply"  # 转供电合同
    NDA = "nda"  # 保密协议
    SERVICE = "service"  # 服务合同
    CONSTRUCTION = "construction"  # 工程合同
    LABOR = "labor"  # 劳动合同
    OTHER = "other"  # 其他


class ContractStatus(str, enum.Enum):
    DRAFT = "draft"  # 草稿
    PENDING_REVIEW = "pending_review"  # 待审查
    REVIEWING = "reviewing"  # 审查中
    REVIEWED = "reviewed"  # 已审查
    PENDING_APPROVAL = "pending_approval"  # 待审批
    APPROVED = "approved"  # 已通过
    REJECTED = "rejected"  # 已驳回
    ARCHIVED = "archived"  # 已归档
    CANCELLED = "cancelled"  # 已取消


class Contract(Base):
    __tablename__ = "contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_no = Column(String(50), unique=True, index=True)  # 合同编号
    title = Column(String(200), nullable=False, index=True)
    contract_type = Column(Enum(ContractType), nullable=False, index=True)
    status = Column(Enum(ContractStatus), default=ContractStatus.DRAFT, index=True)
    
    # 甲乙方信息
    party_a = Column(String(200))  # 甲方
    party_a_contact = Column(String(50))  # 甲方联系人
    party_a_phone = Column(String(20))  # 甲方电话
    party_b = Column(String(200))  # 乙方
    party_b_contact = Column(String(50))  # 乙方联系人
    party_b_phone = Column(String(20))  # 乙方电话
    
    # 合同金额
    amount = Column(Numeric(15, 2))  # 合同金额
    currency = Column(String(10), default="CNY")  # 币种
    
    # 日期
    sign_date = Column(DateTime)  # 签订日期
    effective_date = Column(DateTime)  # 生效日期
    expiry_date = Column(DateTime)  # 到期日期
    
    # 内容
    description = Column(Text)  # 合同摘要
    key_terms = Column(Text)  # 主要条款
    special_terms = Column(Text)  # 特殊条款
    
    # 文件
    file_path = Column(String(500))
    file_name = Column(String(200))
    file_size = Column(Integer)
    file_type = Column(String(20))
    
    # 风险评估
    risk_level = Column(String(20))  # high, medium, low, none
    risk_score = Column(Integer)  # 0-100
    risk_summary = Column(Text)  # 风险摘要
    
    # 审查信息
    reviewer_id = Column(Integer, ForeignKey("users.id"))
    review_deadline = Column(DateTime)
    reviewed_at = Column(DateTime)
    
    # 审批信息
    approver_id = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    approval_remark = Column(Text)
    
    # 关联
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department = Column(String(50))
    project_name = Column(String(200))
    
    # 元数据
    tags = Column(String(500))  # 标签，逗号分隔
    extra_data = Column(Text)  # JSON格式扩展字段
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    uploader = relationship("User", back_populates="contracts", foreign_keys=[uploader_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    approver = relationship("User", foreign_keys=[approver_id])
    versions = relationship("ContractVersion", back_populates="contract")
    files = relationship("ContractFile", back_populates="contract")
    review_tasks = relationship("ReviewTask", back_populates="contract")
    risk_items = relationship("RiskItem", back_populates="contract")


class ContractVersion(Base):
    __tablename__ = "contract_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    version_no = Column(Integer, nullable=False)  # 版本号
    file_path = Column(String(500))
    file_name = Column(String(200))
    file_size = Column(Integer)
    change_summary = Column(Text)  # 变更摘要
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    contract = relationship("Contract", back_populates="versions")


class ContractFile(Base):
    __tablename__ = "contract_files"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    file_name = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    file_type = Column(String(20))
    description = Column(String(500))
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    contract = relationship("Contract", back_populates="files")


class ContractTag(Base):
    __tablename__ = "contract_tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    color = Column(String(20))
    description = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
