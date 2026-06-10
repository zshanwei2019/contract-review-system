"""
记忆系统数据模型 - 审查案例库、风险模式、领域知识
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class PatternSeverity(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class KnowledgeType(str, enum.Enum):
    LAW = "law"           # 法律法规
    REGULATION = "regulation"  # 行业规范
    CASE = "case"         # 典型案例
    CLAUSE = "clause"     # 标准条款
    BEST_PRACTICE = "best_practice"  # 最佳实践


class ReviewCase(Base):
    """审查案例 - 记忆系统的基石"""
    __tablename__ = "review_cases"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), index=True)
    contract_type = Column(String(50), index=True)
    contract_title = Column(String(200))
    amount = Column(Float)

    # 审查结果
    risk_level = Column(String(20))
    risk_score = Column(Integer)
    key_findings = Column(Text)  # JSON: 关键发现
    review_summary = Column(Text)

    # 人工反馈
    lessons_learned = Column(Text)  # JSON: 经验教训
    human_rating = Column(Integer)  # 人工评分 1-5
    human_comment = Column(Text)   # 人工评语
    is_useful = Column(Boolean)    # 是否有用

    # AI元数据
    is_ai_review = Column(Boolean, default=False)
    ai_model = Column(String(50))
    ai_confidence = Column(Float)

    # 审查人
    reviewer_id = Column(Integer, ForeignKey("users.id"))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contract = relationship("Contract", foreign_keys=[contract_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class RiskPattern(Base):
    """风险模式 - 从历史审查中提取的规律"""
    __tablename__ = "risk_patterns"

    id = Column(Integer, primary_key=True, index=True)
    pattern_name = Column(String(200), nullable=False)
    pattern_type = Column(String(50), index=True)  # category: 合同主体/价款与支付等
    description = Column(Text)
    severity = Column(Enum(PatternSeverity), default=PatternSeverity.MEDIUM)
    contract_types = Column(String(500))  # 适用合同类型，逗号分隔

    # 统计
    frequency = Column(Integer, default=1)       # 出现频次
    last_seen = Column(DateTime, default=datetime.utcnow)

    # 应对策略
    recommendation = Column(Text)  # 建议处理方式
    legal_basis = Column(Text)     # 法律依据
    example_clause = Column(Text)  # 示例条款

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContractKnowledge(Base):
    """合同领域知识库"""
    __tablename__ = "contract_knowledge"

    id = Column(Integer, primary_key=True, index=True)
    contract_type = Column(String(50), index=True)
    knowledge_type = Column(Enum(KnowledgeType), index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(200))   # 来源

    # 可用性
    usefulness_score = Column(Float, default=0.0)  # 有用性评分
    use_count = Column(Integer, default=0)         # 使用次数

    # 关联
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User", foreign_keys=[created_by])


class CorrectionLog(Base):
    """人工修正记录 - 反馈闭环的核心"""
    __tablename__ = "correction_logs"

    id = Column(Integer, primary_key=True, index=True)
    review_case_id = Column(Integer, ForeignKey("review_cases.id"), index=True)
    corrector_id = Column(Integer, ForeignKey("users.id"))

    # 修正内容
    original_opinion = Column(Text)    # AI原始意见
    corrected_opinion = Column(Text)   # 修正后意见
    correction_reason = Column(Text)   # 修正原因
    correction_type = Column(String(50))  # 修改/删除/新增

    # 学习状态
    is_learned = Column(Boolean, default=False)  # 是否已学习
    learned_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    review_case = relationship("ReviewCase", foreign_keys=[review_case_id])
    corrector = relationship("User", foreign_keys=[corrector_id])


class AgentMessage(Base):
    """Agent间通信记录"""
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, index=True)
    review_case_id = Column(Integer, ForeignKey("review_cases.id"), index=True)

    from_agent = Column(String(50), nullable=False)  # legal/finance/business
    to_agent = Column(String(50))                      # None = broadcast
    message_type = Column(String(50))                  # finding/question/suggestion
    content = Column(Text, nullable=False)
    extra_metadata = Column(Text)  # JSON

    created_at = Column(DateTime, default=datetime.utcnow)
