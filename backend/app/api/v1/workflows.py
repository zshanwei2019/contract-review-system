from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.workflow import (
    WorkflowDefinition, WorkflowInstance, WorkflowStep,
    WorkflowStatus, InstanceStatus, StepStatus,
)
from app.models.contract import Contract, ContractStatus
from app.schemas.workflow import (
    WorkflowDefinitionCreate, WorkflowDefinitionResponse,
    WorkflowInstanceCreate, WorkflowInstanceResponse,
    WorkflowStepResponse, WorkflowActionRequest,
)
from sqlalchemy.orm import selectinload

router = APIRouter()


@router.get("/definitions", response_model=list[WorkflowDefinitionResponse])
async def list_workflow_definitions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取工作流定义列表"""
    result = await db.execute(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.status == WorkflowStatus.ACTIVE)
        .order_by(WorkflowDefinition.created_at.desc())
    )
    definitions = result.scalars().all()
    return definitions


@router.post("/definitions", response_model=WorkflowDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_definition(
    definition_data: WorkflowDefinitionCreate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """创建工作流定义"""
    definition = WorkflowDefinition(
        name=definition_data.name,
        code=definition_data.code,
        description=definition_data.description,
        contract_type=definition_data.contract_type,
        steps_definition=definition_data.steps_definition,
        conditions=definition_data.conditions,
        created_by=current_user.id,
    )
    db.add(definition)
    await db.commit()
    await db.refresh(definition)
    
    return definition


@router.get("/instances", response_model=list[WorkflowInstanceResponse])
async def list_workflow_instances(
    contract_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取工作流实例列表"""
    query = (
        select(WorkflowInstance)
        .options(selectinload(WorkflowInstance.steps))
        .order_by(WorkflowInstance.created_at.desc())
    )
    if contract_id:
        query = query.where(WorkflowInstance.contract_id == contract_id)
    if status:
        query = query.where(WorkflowInstance.status == InstanceStatus(status))
    
    result = await db.execute(query)
    instances = result.scalars().unique().all()
    return instances


@router.post("/instances", response_model=WorkflowInstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_instance(
    instance_data: WorkflowInstanceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建工作流实例"""
    # Check workflow definition exists
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == instance_data.workflow_id)
    )
    definition = result.scalar_one_or_none()
    
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="工作流定义不存在",
        )
    
    # Check contract exists
    contract_result = await db.execute(
        select(Contract).where(Contract.id == instance_data.contract_id)
    )
    contract = contract_result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )
    
    # Create instance
    instance = WorkflowInstance(
        workflow_id=instance_data.workflow_id,
        contract_id=instance_data.contract_id,
        initiator_id=current_user.id,
        status=InstanceStatus.RUNNING,
        current_step=1,
    )
    db.add(instance)
    await db.flush()
    
    # Create steps from definition
    import json
    steps_def = json.loads(definition.steps_definition) if definition.steps_definition else []
    for step_def in steps_def:
        step = WorkflowStep(
            instance_id=instance.id,
            step_no=step_def.get("step_no", 1),
            step_type=step_def.get("step_type", "review"),
            name=step_def.get("name", "审查"),
            assignee_id=step_def.get("assignee_id"),
            assignee_type=step_def.get("assignee_type", "user"),
        )
        db.add(step)
    
    # Update contract status
    contract.status = ContractStatus.PENDING_APPROVAL
    
    await db.commit()
    await db.refresh(instance)
    
    return instance


@router.get("/instances/{instance_id}", response_model=WorkflowInstanceResponse)
async def get_workflow_instance(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取工作流实例详情"""
    result = await db.execute(
        select(WorkflowInstance).where(WorkflowInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="工作流实例不存在",
        )
    
    return instance


@router.post("/instances/{instance_id}/steps/{step_id}/action")
async def workflow_step_action(
    instance_id: int,
    step_id: int,
    action_data: WorkflowActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """工作流步骤操作（通过/驳回/退回）"""
    # Get instance
    instance_result = await db.execute(
        select(WorkflowInstance).where(WorkflowInstance.id == instance_id)
    )
    instance = instance_result.scalar_one_or_none()
    
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="工作流实例不存在",
        )
    
    if instance.status != InstanceStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="工作流实例不在运行中",
        )
    
    # Get step
    step_result = await db.execute(
        select(WorkflowStep).where(WorkflowStep.id == step_id)
    )
    step = step_result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="工作流步骤不存在",
        )
    
    # Check permission
    if step.assignee_id and step.assignee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此步骤",
        )
    
    # Update step
    step.status = StepStatus.APPROVED if action_data.action == "approve" else StepStatus.REJECTED
    step.result = action_data.action
    step.remark = action_data.remark
    step.completed_at = datetime.utcnow()
    
    # Handle action
    if action_data.action == "approve":
        # Move to next step
        next_step_result = await db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.instance_id == instance_id)
            .where(WorkflowStep.step_no == instance.current_step + 1)
        )
        next_step = next_step_result.scalar_one_or_none()
        
        if next_step:
            instance.current_step += 1
            next_step.started_at = datetime.utcnow()
        else:
            # Workflow completed
            instance.status = InstanceStatus.COMPLETED
            instance.completed_at = datetime.utcnow()
            
            # Update contract status
            contract_result = await db.execute(
                select(Contract).where(Contract.id == instance.contract_id)
            )
            contract = contract_result.scalar_one_or_none()
            if contract:
                contract.status = ContractStatus.APPROVED
                contract.approved_at = datetime.utcnow()
    
    elif action_data.action == "reject":
        instance.status = InstanceStatus.REJECTED
        instance.completed_at = datetime.utcnow()
        
        # Update contract status
        contract_result = await db.execute(
            select(Contract).where(Contract.id == instance.contract_id)
        )
        contract = contract_result.scalar_one_or_none()
        if contract:
            contract.status = ContractStatus.REJECTED
    
    elif action_data.action == "return":
        # Return to previous step
        if instance.current_step > 1:
            instance.current_step -= 1
    
    await db.commit()
    
    return {"message": "操作成功"}
