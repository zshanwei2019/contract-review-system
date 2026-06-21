import json
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.contract import Contract, ContractType, ContractStatus
from app.models.contract_template import ContractTemplate, TemplateStatus
from app.schemas.contract_template import (
    ContractTemplateCreate, ContractTemplateUpdate,
    ContractTemplateResponse, TemplateInstantiateRequest,
)

router = APIRouter()


@router.get("", response_model=list[ContractTemplateResponse])
async def list_templates(
    contract_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取模板列表"""
    query = select(ContractTemplate).order_by(ContractTemplate.updated_at.desc())
    if contract_type:
        query = query.where(ContractTemplate.contract_type == contract_type)
    if status:
        query = query.where(ContractTemplate.status == TemplateStatus(status))
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=ContractTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: ContractTemplateCreate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """创建模板"""
    template = ContractTemplate(
        name=data.name,
        description=data.description,
        contract_type=data.contract_type,
        content=data.content,
        clauses=data.clauses,
        variables=data.variables,
        created_by=current_user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/{template_id}", response_model=ContractTemplateResponse)
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取模板详情"""
    result = await db.execute(select(ContractTemplate).where(ContractTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return template


@router.put("/{template_id}", response_model=ContractTemplateResponse)
async def update_template(
    template_id: int,
    data: ContractTemplateUpdate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """更新模板"""
    result = await db.execute(select(ContractTemplate).where(ContractTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    template.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """删除模板"""
    result = await db.execute(select(ContractTemplate).where(ContractTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    await db.delete(template)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/{template_id}/publish", response_model=ContractTemplateResponse)
async def publish_template(
    template_id: int,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """发布模板"""
    result = await db.execute(select(ContractTemplate).where(ContractTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    template.status = TemplateStatus.PUBLISHED
    template.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(template)
    return template


@router.post("/{template_id}/instantiate")
async def instantiate_template(
    template_id: int,
    data: TemplateInstantiateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从模板创建合同"""
    result = await db.execute(select(ContractTemplate).where(ContractTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    if template.status != TemplateStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="模板未发布")
    
    # 替换变量
    content = template.content
    for var_name, var_value in data.variables.items():
        content = content.replace(f"{{{{{var_name}}}}}", str(var_value))
    
    # 检查未替换的变量
    remaining = re.findall(r"\{\{(\w+)\}\}", content)
    if remaining:
        raise HTTPException(status_code=400, detail=f"以下变量未提供值: {', '.join(remaining)}")
    
    # 创建合同
    contract = Contract(
        title=data.title or f"从模板创建 - {template.name}",
        contract_type=ContractType(template.contract_type),
        status=ContractStatus.DRAFT,
        description=content[:500],
        key_terms=content,
        uploader_id=current_user.id,
    )
    db.add(contract)
    
    # 增加使用次数
    template.usage_count = (template.usage_count or 0) + 1
    
    await db.commit()
    await db.refresh(contract)
    return {"message": "合同创建成功", "contract_id": contract.id}
