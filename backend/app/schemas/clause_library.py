from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ClauseLibraryBase(BaseModel):
    title: str
    category: str
    content: str
    contract_type: Optional[str] = None
    risk_level: str = "low"
    tags: Optional[str] = None


class ClauseLibraryCreate(ClauseLibraryBase):
    pass


class ClauseLibraryUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    contract_type: Optional[str] = None
    risk_level: Optional[str] = None
    tags: Optional[str] = None


class ClauseLibraryResponse(ClauseLibraryBase):
    id: int
    source: str
    usage_count: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = False

    class Config:
        from_attributes = True
