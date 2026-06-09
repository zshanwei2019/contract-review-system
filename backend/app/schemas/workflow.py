from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models.workflow import WorkflowStatus, InstanceStatus, StepType, StepStatus


class WorkflowDefinitionBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    contract_type: Optional[str] = None
    steps_definition: Optional[str] = None
    conditions: Optional[str] = None


class WorkflowDefinitionCreate(WorkflowDefinitionBase):
    pass


class WorkflowDefinitionResponse(WorkflowDefinitionBase):
    id: int
    status: WorkflowStatus
    version: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowInstanceBase(BaseModel):
    workflow_id: int
    contract_id: int


class WorkflowInstanceCreate(WorkflowInstanceBase):
    pass


class WorkflowInstanceResponse(WorkflowInstanceBase):
    id: int
    status: InstanceStatus
    current_step: Optional[int] = None
    initiator_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    steps: List["WorkflowStepResponse"] = []

    class Config:
        from_attributes = True


class WorkflowStepBase(BaseModel):
    step_no: int
    step_type: StepType
    name: str
    assignee_id: Optional[int] = None
    assignee_type: Optional[str] = None
    deadline: Optional[datetime] = None


class WorkflowStepCreate(WorkflowStepBase):
    instance_id: int


class WorkflowStepUpdate(BaseModel):
    status: Optional[StepStatus] = None
    result: Optional[str] = None
    remark: Optional[str] = None


class WorkflowStepResponse(WorkflowStepBase):
    id: int
    instance_id: int
    status: StepStatus
    result: Optional[str] = None
    remark: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WorkflowActionRequest(BaseModel):
    action: str  # approve, reject, return
    remark: Optional[str] = None
