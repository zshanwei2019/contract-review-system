from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.contract import Contract, ContractStatus
from app.models.review import ReviewTask, ReviewTaskStatus, ReviewResult, ReviewOpinion
from app.schemas.review import (
    ReviewTaskCreate,
    ReviewTaskUpdate,
    ReviewTaskResponse,
    ReviewTaskList,
    ReviewOpinionCreate,
    ReviewOpinionResponse,
)

router = APIRouter()


@router.get("", response_model=ReviewTaskList)
async def list_review_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[ReviewTaskStatus] = None,
    contract_id: Optional[int] = None,
    reviewer_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取审查任务列表"""
    query = select(ReviewTask)
    count_query = select(func.count()).select_from(ReviewTask)
    
    if status:
        query = query.where(ReviewTask.status == status)
        count_query = count_query.where(ReviewTask.status == status)
    
    if contract_id:
        query = query.where(ReviewTask.contract_id == contract_id)
        count_query = count_query.where(ReviewTask.contract_id == contract_id)
    
    if reviewer_id:
        query = query.where(ReviewTask.reviewer_id == reviewer_id)
        count_query = count_query.where(ReviewTask.reviewer_id == reviewer_id)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    query = query.order_by(ReviewTask.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return ReviewTaskList(total=total, items=tasks)


@router.post("", response_model=ReviewTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_review_task(
    task_data: ReviewTaskCreate,
    current_user: User = Depends(require_role("admin", "superadmin", "reviewer")),
    db: AsyncSession = Depends(get_db),
):
    """创建审查任务"""
    # Check contract exists
    contract_result = await db.execute(
        select(Contract).where(Contract.id == task_data.contract_id)
    )
    contract = contract_result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    # Create task
    task = ReviewTask(
        contract_id=task_data.contract_id,
        reviewer_id=task_data.reviewer_id,
        assigned_by=current_user.id,
        deadline=task_data.deadline,
        status=ReviewTaskStatus.PENDING,
    )
    db.add(task)
    
    # Update contract status
    contract.status = ContractStatus.REVIEWING
    
    await db.commit()
    await db.refresh(task)
    
    return task


@router.get("/{task_id}", response_model=ReviewTaskResponse)
async def get_review_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取审查任务详情"""
    result = await db.execute(select(ReviewTask).where(ReviewTask.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="审查任务不存在",
        )
    
    return task


@router.put("/{task_id}", response_model=ReviewTaskResponse)
async def update_review_task(
    task_id: int,
    task_data: ReviewTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新审查任务"""
    result = await db.execute(select(ReviewTask).where(ReviewTask.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="审查任务不存在",
        )
    
    # Check permission
    if task.reviewer_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能更新自己的审查任务",
        )
    
    # Update fields
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    # Update timestamps
    if task_data.status == ReviewTaskStatus.IN_PROGRESS and not task.started_at:
        task.started_at = datetime.utcnow()
    
    if task_data.status == ReviewTaskStatus.COMPLETED:
        task.completed_at = datetime.utcnow()
        
        # Update contract status
        contract_result = await db.execute(
            select(Contract).where(Contract.id == task.contract_id)
        )
        contract = contract_result.scalar_one_or_none()
        if contract:
            contract.status = ContractStatus.REVIEWED
            contract.reviewed_at = datetime.utcnow()
            contract.risk_level = task.risk_level
            contract.risk_score = task.risk_score
    
    await db.commit()
    await db.refresh(task)
    
    return task


@router.post("/{task_id}/opinions", response_model=ReviewOpinionResponse, status_code=status.HTTP_201_CREATED)
async def create_review_opinion(
    task_id: int,
    opinion_data: ReviewOpinionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建审查意见"""
    # Check task exists
    result = await db.execute(select(ReviewTask).where(ReviewTask.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="审查任务不存在",
        )
    
    opinion = ReviewOpinion(
        review_task_id=task_id,
        reviewer_id=current_user.id,
        opinion_type=opinion_data.opinion_type,
        content=opinion_data.content,
        suggestion=opinion_data.suggestion,
        risk_level=opinion_data.risk_level,
        clause_reference=opinion_data.clause_reference,
        legal_basis=opinion_data.legal_basis,
    )
    db.add(opinion)
    await db.commit()
    await db.refresh(opinion)
    
    return opinion


@router.get("/{task_id}/opinions", response_model=list[ReviewOpinionResponse])
async def list_review_opinions(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取审查意见列表"""
    result = await db.execute(
        select(ReviewOpinion)
        .where(ReviewOpinion.review_task_id == task_id)
        .order_by(ReviewOpinion.created_at.desc())
    )
    opinions = result.scalars().all()
    return opinions
