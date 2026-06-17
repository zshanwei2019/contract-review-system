from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class RiskLevel(str, enum.Enum):
    HIGH = "high"  # 高风险
    MEDIUM = "medium"  # 中风险
    LOW = "low"  # 低风险
    NONE = "none"  # 无风险


class RiskCategory(Base):
    __tablename__ = "risk_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    parent_id = Column(Integer)
    icon = Column(String(50))
    color = Column(String(20))
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    rules = relationship("RiskRule", back_populates="category")


class RiskRule(Base):
    __tablename__ = "risk_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("risk_categories.id"), nullable=False)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    
    # 规则定义
    rule_type = Column(String(50))  # keyword, regex, ai, logic
    rule_config = Column(Text)  # JSON格式规则配置
    
    # 风险等级
    risk_level = Column(Enum(RiskLevel), nullable=False)
    risk_score = Column(Integer)  # 0-100
    
    # 四维权重配置 (默认: severity=40%, likelihood=25%, financial=20%, responsibility=15%)
    weight_severity = Column(Float, default=0.40)
    weight_likelihood = Column(Float, default=0.25)
    weight_financial = Column(Float, default=0.20)
    weight_responsibility = Column(Float, default=0.15)
    
    # 建议
    suggestion = Column(Text)
    legal_basis = Column(Text)
    
    # 适用范围
    contract_type = Column(String(50))  # 适用合同类型
    is_active = Column(Boolean, default=True)
    
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = relationship("RiskCategory", back_populates="rules")


class RiskItem(Base):
    __tablename__ = "risk_items"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    rule_id = Column(Integer, ForeignKey("risk_rules.id"))
    review_task_id = Column(Integer, ForeignKey("review_tasks.id"))
    
    # 风险信息
    title = Column(String(200))  # 风险标题
    risk_level = Column(Enum(RiskLevel), nullable=False)
    risk_category = Column(String(100))
    risk_description = Column(Text, nullable=False)
    
    # 条款定位 (from previous session)
    clause_text = Column(Text)  # 条款原文
    clause_location = Column(String(500))  # 条款位置描述
    confidence = Column(Float)  # AI识别置信度 0-1
    
    # 位置
    clause_reference = Column(String(200))  # 条款引用
    page_number = Column(Integer)
    position = Column(Text)  # JSON格式位置信息
    
    # === 风险量化评估字段 ===
    # 四维评分 (0-100)
    score_severity = Column(Integer)       # 严重性评分
    score_likelihood = Column(Integer)     # 可能性评分
    score_financial = Column(Integer)      # 财务风险敞口评分
    score_responsibility = Column(Integer) # 责任不对称性评分
    # 综合风险评分 (加权计算)
    risk_score = Column(Integer)           # 0-100 综合评分
    # 财务影响
    potential_loss_min = Column(Float)     # 最小潜在损失(元)
    potential_loss_max = Column(Float)     # 最大潜在损失(元)
    loss_probability = Column(Float)       # 损失概率 0-1
    expected_loss = Column(Float)          # 期望损失 = max * probability
    # 量化分析详情
    quantification_detail = Column(JSON)   # JSON格式量化分析详情
    
    # 建议
    suggestion = Column(Text)
    legal_basis = Column(Text)
    
    # 状态
    is_confirmed = Column(Boolean, default=False)  # 是否确认
    is_resolved = Column(Boolean, default=False)  # 是否解决
    resolved_by = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    resolution_note = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contract = relationship("Contract", back_populates="risk_items")
    rule = relationship("RiskRule")
