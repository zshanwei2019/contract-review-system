from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class SealResponse(BaseModel):
    id: int
    name: str
    seal_type: str
    image_url: str
    is_active: bool
    certificate_sn: Optional[str] = None
    certificate_expiry: Optional[datetime] = None
    owner_id: Optional[int] = None
    created_at: datetime
    class Config:
        from_attributes = True


class SealCreate(BaseModel):
    name: str
    seal_type: str
    image_url: str
    certificate_sn: Optional[str] = None
    certificate_expiry: Optional[datetime] = None


class SignatureRequestResponse(BaseModel):
    id: int
    contract_id: int
    signer_name: str
    signer_email: Optional[str] = None
    signer_phone: Optional[str] = None
    signature_type: str
    position: Optional[str] = None
    seal_image_url: Optional[str] = None
    status: str
    signed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    certificate_sn: Optional[str] = None
    certificate_issuer: Optional[str] = None
    hash_value: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


class SignatureRequestCreate(BaseModel):
    contract_id: int
    signer_name: str
    signer_email: Optional[str] = None
    signer_phone: Optional[str] = None
    signer_id_number: Optional[str] = None
    signature_type: str = "enterprise"
    position: Optional[str] = None
    seal_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    remark: Optional[str] = None
