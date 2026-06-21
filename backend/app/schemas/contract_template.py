from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class TemplateVariable(BaseModel):
    name: str
    label: str
    required: bool = True
    default: Optional[str] = None


class ContractTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    contract_type: str
    content: str
    clauses: Optional[str] = None  # JSON string
    variables: Optional[str] = None  # JSON string


class ContractTemplateCreate(ContractTemplateBase):
    pass


class ContractTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    clauses: Optional[str] = None
    variables: Optional[str] = None
    status: Optional[str] = None


class ContractTemplateResponse(ContractTemplateBase):
    id: int
    status: str
    version: int
    usage_count: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateInstantiateRequest(BaseModel):
    variables: dict  # 变量名 -> 值
    title: Optional[str] = None  # 合同标题, 可选
