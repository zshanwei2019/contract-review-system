from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.models.contract import ContractType, ContractStatus


class ContractBase(BaseModel):
    title: str
    contract_type: ContractType
    party_a: Optional[str] = None
    party_b: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: str = "CNY"
    sign_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    description: Optional[str] = None
    department: Optional[str] = None
    project_name: Optional[str] = None
    tags: Optional[str] = None


class ContractCreate(ContractBase):
    pass


class ContractUpdate(BaseModel):
    title: Optional[str] = None
    contract_type: Optional[ContractType] = None
    party_a: Optional[str] = None
    party_a_contact: Optional[str] = None
    party_a_phone: Optional[str] = None
    party_b: Optional[str] = None
    party_b_contact: Optional[str] = None
    party_b_phone: Optional[str] = None
    amount: Optional[Decimal] = None
    sign_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    description: Optional[str] = None
    key_terms: Optional[str] = None
    special_terms: Optional[str] = None
    department: Optional[str] = None
    project_name: Optional[str] = None
    tags: Optional[str] = None
    reviewer_id: Optional[int] = None
    review_deadline: Optional[datetime] = None


class ContractResponse(ContractBase):
    id: int
    contract_no: Optional[str] = None
    status: ContractStatus
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    risk_summary: Optional[str] = None
    uploader_id: int
    uploader_name: Optional[str] = None
    reviewer_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContractList(BaseModel):
    total: int
    items: List[ContractResponse]


class ContractVersionResponse(BaseModel):
    id: int
    contract_id: int
    version_no: int
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    change_summary: Optional[str] = None
    uploaded_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ContractFileResponse(BaseModel):
    id: int
    contract_id: int
    file_name: str
    file_path: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    description: Optional[str] = None
    uploaded_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ContractUploadResponse(BaseModel):
    id: int
    file_name: str
    file_path: str
    status: str
    message: str
