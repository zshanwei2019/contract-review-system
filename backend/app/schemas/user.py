from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: EmailStr
    name: str
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role_ids: Optional[List[int]] = []


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    avatar: Optional[str] = None
    is_active: Optional[bool] = None
    role_ids: Optional[List[int]] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    avatar: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    roles: List[str] = []

    class Config:
        from_attributes = True


class UserList(BaseModel):
    total: int
    items: List[UserResponse]


class RoleBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    permission_ids: Optional[List[int]] = []


class RoleResponse(RoleBase):
    id: int
    is_active: bool
    created_at: datetime
    permissions: List[str] = []

    class Config:
        from_attributes = True


class PermissionResponse(BaseModel):
    id: int
    name: str
    code: str
    type: str
    path: Optional[str] = None
    icon: Optional[str] = None

    class Config:
        from_attributes = True
