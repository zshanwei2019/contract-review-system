from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

from app.models.risk import RiskLevel


class RiskCategoryBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class RiskCategoryCreate(RiskCategoryBase):
    pass


class RiskCategoryResponse(RiskCategoryBase):
    id: int
    is_active: bool
    sort_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class RiskRuleBase(BaseModel):
    category_id: int
    name: str
    code: str
    description: Optional[str] = None
    rule_type: str
    rule_config: str
    risk_level: RiskLevel
    risk_score: int
    suggestion: Optional[str] = None
    legal_basis: Optional[str] = None
    contract_type: Optional[str] = None


class RiskRuleCreate(RiskRuleBase):
    weight_severity: Optional[float] = 0.40
    weight_likelihood: Optional[float] = 0.25
    weight_financial: Optional[float] = 0.20
    weight_responsibility: Optional[float] = 0.15


class RiskRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_config: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    risk_score: Optional[int] = None
    suggestion: Optional[str] = None
    legal_basis: Optional[str] = None
    is_active: Optional[bool] = None
    weight_severity: Optional[float] = None
    weight_likelihood: Optional[float] = None
    weight_financial: Optional[float] = None
    weight_responsibility: Optional[float] = None


class RiskRuleResponse(RiskRuleBase):
    id: int
    is_active: bool
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    category_name: Optional[str] = None
    weight_severity: Optional[float] = None
    weight_likelihood: Optional[float] = None
    weight_financial: Optional[float] = None
    weight_responsibility: Optional[float] = None

    class Config:
        from_attributes = True


class RiskRuleList(BaseModel):
    total: int
    items: List[RiskRuleResponse]


class RiskItemBase(BaseModel):
    risk_level: RiskLevel
    risk_category: Optional[str] = None
    risk_description: str
    clause_reference: Optional[str] = None
    suggestion: Optional[str] = None
    legal_basis: Optional[str] = None


class RiskItemCreate(RiskItemBase):
    contract_id: int
    rule_id: Optional[int] = None
    review_task_id: Optional[int] = None
    # 条款定位
    clause_text: Optional[str] = None
    clause_location: Optional[str] = None
    confidence: Optional[float] = None
    # 量化评估
    score_severity: Optional[int] = None
    score_likelihood: Optional[int] = None
    score_financial: Optional[int] = None
    score_responsibility: Optional[int] = None
    risk_score: Optional[int] = None
    potential_loss_min: Optional[float] = None
    potential_loss_max: Optional[float] = None
    loss_probability: Optional[float] = None
    expected_loss: Optional[float] = None
    quantification_detail: Optional[Any] = None


class RiskItemUpdate(BaseModel):
    is_confirmed: Optional[bool] = None
    is_resolved: Optional[bool] = None
    resolution_note: Optional[str] = None
    # 量化评估更新
    score_severity: Optional[int] = None
    score_likelihood: Optional[int] = None
    score_financial: Optional[int] = None
    score_responsibility: Optional[int] = None
    risk_score: Optional[int] = None
    potential_loss_min: Optional[float] = None
    potential_loss_max: Optional[float] = None
    loss_probability: Optional[float] = None
    expected_loss: Optional[float] = None
    quantification_detail: Optional[Any] = None


class RiskItemResponse(RiskItemBase):
    id: int
    contract_id: int
    rule_id: Optional[int] = None
    review_task_id: Optional[int] = None
    # 条款定位
    clause_text: Optional[str] = None
    clause_location: Optional[str] = None
    confidence: Optional[float] = None
    # 量化评估
    score_severity: Optional[int] = None
    score_likelihood: Optional[int] = None
    score_financial: Optional[int] = None
    score_responsibility: Optional[int] = None
    risk_score: Optional[int] = None
    potential_loss_min: Optional[float] = None
    potential_loss_max: Optional[float] = None
    loss_probability: Optional[float] = None
    expected_loss: Optional[float] = None
    quantification_detail: Optional[Any] = None
    # 位置
    page_number: Optional[int] = None
    # 状态
    is_confirmed: bool
    is_resolved: bool
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RiskItemList(BaseModel):
    total: int
    items: List[RiskItemResponse]


class RiskAnalysisResult(BaseModel):
    contract_id: int
    overall_risk: RiskLevel
    risk_score: int
    risk_summary: str
    risk_items: List[RiskItemResponse]
    analyzed_at: datetime


# === 风险量化专用Schema ===

class RiskQuantificationRequest(BaseModel):
    """风险量化评估请求"""
    risk_item_id: int
    contract_value: Optional[float] = None  # 合同金额，用于估算财务影响


class RiskQuantificationResponse(BaseModel):
    """风险量化评估响应"""
    risk_item_id: int
    risk_score: int
    risk_level: str
    score_severity: int
    score_likelihood: int
    score_financial: int
    score_responsibility: int
    potential_loss_min: Optional[float] = None
    potential_loss_max: Optional[float] = None
    loss_probability: Optional[float] = None
    expected_loss: Optional[float] = None
    quantification_detail: Optional[Any] = None


class ContractRiskSummary(BaseModel):
    """合同风险汇总"""
    contract_id: int
    total_risks: int
    high_risks: int
    medium_risks: int
    low_risks: int
    overall_score: int
    overall_level: str
    total_expected_loss: float
    risk_items: List[RiskItemResponse]
