from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.clause_library import ClauseLibrary, ClauseFavorite
from app.schemas.clause_library import (
    ClauseLibraryCreate, ClauseLibraryUpdate, ClauseLibraryResponse,
)

router = APIRouter()


@router.get("", response_model=list[ClauseLibraryResponse])
async def list_clauses(
    category: Optional[str] = None,
    contract_type: Optional[str] = None,
    keyword: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取条款库列表"""
    query = select(ClauseLibrary).order_by(ClauseLibrary.usage_count.desc(), ClauseLibrary.created_at.desc())
    if category:
        query = query.where(ClauseLibrary.category == category)
    if contract_type:
        query = query.where(
            or_(
                ClauseLibrary.contract_type == contract_type,
                ClauseLibrary.contract_type.is_(None),
            )
        )
    if keyword:
        query = query.where(
            or_(
                ClauseLibrary.title.ilike(f"%{keyword}%"),
                ClauseLibrary.content.ilike(f"%{keyword}%"),
                ClauseLibrary.tags.ilike(f"%{keyword}%"),
            )
        )
    
    result = await db.execute(query)
    clauses = result.scalars().all()
    
    # 查询用户收藏
    fav_result = await db.execute(
        select(ClauseFavorite.clause_id).where(ClauseFavorite.user_id == current_user.id)
    )
    fav_ids = set(fav_result.scalars().all())
    
    responses = []
    for c in clauses:
        resp = ClauseLibraryResponse.model_validate(c)
        resp.is_favorite = c.id in fav_ids
        responses.append(resp)
    return responses


@router.post("", response_model=ClauseLibraryResponse, status_code=status.HTTP_201_CREATED)
async def create_clause(
    data: ClauseLibraryCreate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """创建条款"""
    clause = ClauseLibrary(
        title=data.title,
        category=data.category,
        content=data.content,
        contract_type=data.contract_type,
        risk_level=data.risk_level,
        tags=data.tags,
        source="custom",
        created_by=current_user.id,
    )
    db.add(clause)
    await db.commit()
    await db.refresh(clause)
    return clause


@router.put("/{clause_id}", response_model=ClauseLibraryResponse)
async def update_clause(
    clause_id: int,
    data: ClauseLibraryUpdate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """更新条款"""
    result = await db.execute(select(ClauseLibrary).where(ClauseLibrary.id == clause_id))
    clause = result.scalar_one_or_none()
    if not clause:
        raise HTTPException(status_code=404, detail="条款不存在")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(clause, field, value)
    clause.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(clause)
    return clause


@router.delete("/{clause_id}")
async def delete_clause(
    clause_id: int,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """删除条款"""
    result = await db.execute(select(ClauseLibrary).where(ClauseLibrary.id == clause_id))
    clause = result.scalar_one_or_none()
    if not clause:
        raise HTTPException(status_code=404, detail="条款不存在")
    
    await db.delete(clause)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/{clause_id}/favorite")
async def favorite_clause(
    clause_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """收藏条款"""
    # 检查是否已收藏
    existing = await db.execute(
        select(ClauseFavorite).where(
            ClauseFavorite.user_id == current_user.id,
            ClauseFavorite.clause_id == clause_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "已收藏"}
    
    fav = ClauseFavorite(user_id=current_user.id, clause_id=clause_id)
    db.add(fav)
    await db.commit()
    return {"message": "收藏成功"}


@router.delete("/{clause_id}/favorite")
async def unfavorite_clause(
    clause_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消收藏"""
    result = await db.execute(
        select(ClauseFavorite).where(
            ClauseFavorite.user_id == current_user.id,
            ClauseFavorite.clause_id == clause_id,
        )
    )
    fav = result.scalar_one_or_none()
    if fav:
        await db.delete(fav)
        await db.commit()
    return {"message": "已取消收藏"}


@router.get("/favorites", response_model=list[ClauseLibraryResponse])
async def list_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取我的收藏"""
    result = await db.execute(
        select(ClauseLibrary)
        .join(ClauseFavorite, ClauseFavorite.clause_id == ClauseLibrary.id)
        .where(ClauseFavorite.user_id == current_user.id)
        .order_by(ClauseFavorite.created_at.desc())
    )
    clauses = result.scalars().all()
    responses = []
    for c in clauses:
        resp = ClauseLibraryResponse.model_validate(c)
        resp.is_favorite = True
        responses.append(resp)
    return responses
