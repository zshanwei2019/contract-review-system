from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models.review import ReviewTaskStatus, ReviewResult


class ReviewTaskBase(BaseModel):
    contract_id: int
    reviewer_id: int
    deadline: Optional[datetime] = None


class ReviewTaskCreate(ReviewTaskBase):
    pass


class ReviewTaskUpdate(BaseModel):
    status: Optional[ReviewTaskStatus] = None
    result: Optional[ReviewResult] = None
    review_opinion: Optional[str] = None
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    summary: Optional[str] = None


class ReviewTaskResponse(ReviewTaskBase):
    id: int
    status: ReviewTaskStatus
    result: Optional[ReviewResult] = None
    review_opinion: Optional[str] = None
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    summary: Optional[str] = None
    assigned_by: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    contract_title: Optional[str] = None
    reviewer_name: Optional[str] = None

    class Config:
        from_attributes = True


class ReviewTaskList(BaseModel):
    total: int
    items: List[ReviewTaskResponse]


class ReviewOpinionBase(BaseModel):
    opinion_type: str
    content: str
    suggestion: Optional[str] = None
    risk_level: Optional[str] = None
    clause_reference: Optional[str] = None
    legal_basis: Optional[str] = None


class ReviewOpinionCreate(ReviewOpinionBase):
    review_task_id: int


class ReviewOpinionResponse(ReviewOpinionBase):
    id: int
    review_task_id: int
    reviewer_id: int
    reviewer_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewTemplateBase(BaseModel):
    name: str
    contract_type: Optional[str] = None
    description: Optional[str] = None
    checklist: Optional[str] = None
    risk_rules: Optional[str] = None


class ReviewTemplateCreate(ReviewTemplateBase):
    pass


class ReviewTemplateResponse(ReviewTemplateBase):
    id: int
    is_active: bool
    created_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
