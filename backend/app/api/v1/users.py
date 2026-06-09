from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, get_password_hash, require_role
from app.models.user import User, Role, UserRole
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserList,
    RoleCreate,
    RoleResponse,
)

router = APIRouter()


@router.get("", response_model=UserList)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """获取用户列表"""
    query = select(User)
    count_query = select(func.count()).select_from(User)
    
    if keyword:
        query = query.where(
            (User.username.contains(keyword)) |
            (User.name.contains(keyword)) |
            (User.email.contains(keyword))
        )
        count_query = count_query.where(
            (User.username.contains(keyword)) |
            (User.name.contains(keyword)) |
            (User.email.contains(keyword))
        )
    
    if department:
        query = query.where(User.department == department)
        count_query = count_query.where(User.department == department)
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()
    
    return UserList(total=total, items=users)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """创建用户"""
    # Check if username exists
    existing = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    
    # Check if email exists
    existing = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被使用",
        )
    
    # Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        name=user_data.name,
        phone=user_data.phone,
        department=user_data.department,
        position=user_data.position,
    )
    db.add(user)
    await db.flush()
    
    # Assign roles
    if user_data.role_ids:
        for role_id in user_data.role_ids:
            user_role = UserRole(user_id=user.id, role_id=role_id)
            db.add(user_role)
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户详情"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """更新用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    
    # Update fields
    update_data = user_data.model_dump(exclude_unset=True)
    role_ids = update_data.pop("role_ids", None)
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    # Update roles
    if role_ids is not None:
        # Remove existing roles
        await db.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        # Add new roles
        for role_id in role_ids:
            user_role = UserRole(user_id=user_id, role_id=role_id)
            db.add(user_role)
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """删除用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    
    if user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除超级管理员",
        )
    
    await db.delete(user)
    await db.commit()


@router.get("/roles/list", response_model=list[RoleResponse])
async def list_roles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取角色列表"""
    result = await db.execute(select(Role).where(Role.is_active == True))
    roles = result.scalars().all()
    return roles


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """创建角色"""
    role = Role(
        name=role_data.name,
        code=role_data.code,
        description=role_data.description,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    return role
