from pydantic import BaseModel
from typing import Optional, List
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
    pass


class RiskRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_config: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    risk_score: Optional[int] = None
    suggestion: Optional[str] = None
    legal_basis: Optional[str] = None
    is_active: Optional[bool] = None


class RiskRuleResponse(RiskRuleBase):
    id: int
    is_active: bool
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    category_name: Optional[str] = None

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


class RiskItemUpdate(BaseModel):
    is_confirmed: Optional[bool] = None
    is_resolved: Optional[bool] = None
    resolution_note: Optional[str] = None


class RiskItemResponse(RiskItemBase):
    id: int
    contract_id: int
    rule_id: Optional[int] = None
    review_task_id: Optional[int] = None
    page_number: Optional[int] = None
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
