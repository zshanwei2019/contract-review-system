from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.risk import RiskRule, RiskCategory, RiskItem, RiskLevel
from app.schemas.risk import (
    RiskRuleCreate, RiskRuleUpdate, RiskRuleResponse, RiskRuleList,
    RiskCategoryCreate, RiskCategoryResponse,
    RiskItemCreate, RiskItemUpdate, RiskItemResponse, RiskItemList,
)

router = APIRouter()


# Risk Categories
@router.get("/categories", response_model=list[RiskCategoryResponse])
async def list_risk_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取风险分类列表"""
    result = await db.execute(
        select(RiskCategory)
        .where(RiskCategory.is_active == True)
        .order_by(RiskCategory.sort_order)
    )
    categories = result.scalars().all()
    return categories


@router.post("/categories", response_model=RiskCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_risk_category(
    category_data: RiskCategoryCreate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """创建风险分类"""
    category = RiskCategory(**category_data.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


# Risk Rules
@router.get("/rules", response_model=RiskRuleList)
async def list_risk_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    risk_level: Optional[RiskLevel] = None,
    contract_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取风险规则列表"""
    query = select(RiskRule)
    count_query = select(func.count()).select_from(RiskRule)
    
    if category_id:
        query = query.where(RiskRule.category_id == category_id)
        count_query = count_query.where(RiskRule.category_id == category_id)
    
    if risk_level:
        query = query.where(RiskRule.risk_level == risk_level)
        count_query = count_query.where(RiskRule.risk_level == risk_level)
    
    if contract_type:
        query = query.where(RiskRule.contract_type == contract_type)
        count_query = count_query.where(RiskRule.contract_type == contract_type)
    
    if is_active is not None:
        query = query.where(RiskRule.is_active == is_active)
        count_query = count_query.where(RiskRule.is_active == is_active)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    query = query.order_by(RiskRule.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rules = result.scalars().all()
    
    return RiskRuleList(total=total, items=rules)


@router.post("/rules", response_model=RiskRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_risk_rule(
    rule_data: RiskRuleCreate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """创建风险规则"""
    rule = RiskRule(
        **rule_data.model_dump(),
        created_by=current_user.id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=RiskRuleResponse)
async def update_risk_rule(
    rule_id: int,
    rule_data: RiskRuleUpdate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """更新风险规则"""
    result = await db.execute(select(RiskRule).where(RiskRule.id == rule_id))
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="风险规则不存在",
        )
    
    update_data = rule_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)
    
    await db.commit()
    await db.refresh(rule)
    return rule


# Risk Items
@router.get("/items", response_model=RiskItemList)
async def list_risk_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    contract_id: Optional[int] = None,
    risk_level: Optional[RiskLevel] = None,
    is_resolved: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取风险项列表"""
    query = select(RiskItem)
    count_query = select(func.count()).select_from(RiskItem)
    
    if contract_id:
        query = query.where(RiskItem.contract_id == contract_id)
        count_query = count_query.where(RiskItem.contract_id == contract_id)
    
    if risk_level:
        query = query.where(RiskItem.risk_level == risk_level)
        count_query = count_query.where(RiskItem.risk_level == risk_level)
    
    if is_resolved is not None:
        query = query.where(RiskItem.is_resolved == is_resolved)
        count_query = count_query.where(RiskItem.is_resolved == is_resolved)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    from sqlalchemy.orm import selectinload
    query = query.order_by(RiskItem.created_at.desc())
    query = query.options(selectinload(RiskItem.contract))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()
    
    # 手动转换items为字典列表
    item_list = []
    for item in items:
        item_dict = {
            "id": item.id,
            "contract_id": item.contract_id,
            "rule_id": item.rule_id,
            "review_task_id": item.review_task_id,
            "title": item.title,
            "risk_level": item.risk_level.value if item.risk_level else None,
            "risk_category": item.risk_category,
            "risk_description": item.risk_description,
            "clause_reference": item.clause_reference,
            "page_number": item.page_number,
            "suggestion": item.suggestion,
            "legal_basis": item.legal_basis,
            "is_confirmed": item.is_confirmed,
            "is_resolved": item.is_resolved,
            "resolved_by": item.resolved_by,
            "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
            "resolution_note": item.resolution_note,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "contract": {
                "id": item.contract.id,
                "title": item.contract.title,
                "contract_no": item.contract.contract_no,
            } if item.contract else None,
        }
        item_list.append(item_dict)
    
    return RiskItemList(total=total, items=item_list)


@router.put("/items/{item_id}", response_model=RiskItemResponse)
async def update_risk_item(
    item_id: int,
    item_data: RiskItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新风险项"""
    result = await db.execute(select(RiskItem).where(RiskItem.id == item_id))
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="风险项不存在",
        )
    
    update_data = item_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    
    if item_data.is_resolved:
        item.resolved_by = current_user.id
        item.resolved_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/init-rules")
async def init_risk_rules(
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """初始化23条行业风控规则和14种毒丸条款检测规则"""
    from app.services.risk_rules_engine import INDUSTRY_RISK_RULES, POISON_PILL_PATTERNS
    from datetime import datetime
    
    created_count = 0
    
    # 合同类型英文到中文的映射
    contract_type_map = {
        "procurement": "采购合同",
        "sales": "销售合同",
        "outsourcing": "外协合同",
        "lease": "租赁合同",
        "logistics": "物流合同",
        "equipment": "设备合同",
        "service": "服务合同",
        "construction": "建设合同",
        "nda": "保密合同",
        "other": "其他合同",
    }
    
    # 创建风险分类（如果不存在）
    categories = {}
    cat_names = {
        "procurement": "采购类",
        "sales": "销售类",
        "outsourcing": "外协类",
        "lease": "租赁类",
        "logistics": "物流类",
        "all": "通用类",
    }
    
    for code, name in cat_names.items():
        result = await db.execute(
            select(RiskCategory).where(RiskCategory.code == code)
        )
        cat = result.scalar_one_or_none()
        if not cat:
            cat = RiskCategory(
                name=name,
                code=code,
                is_active=True,
                sort_order=list(cat_names.keys()).index(code),
            )
            db.add(cat)
            await db.flush()
        categories[code] = cat
    
    # 导入23条行业风控规则
    for rule in INDUSTRY_RISK_RULES:
        result = await db.execute(
            select(RiskRule).where(RiskRule.code == rule["id"])
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            cat_code = rule["cat"].split(",")[0] if rule["cat"] != "all" else "all"
            category = categories.get(cat_code, categories["all"])
            
            risk_level = "high" if rule["sev"] >= 0.7 else ("medium" if rule["sev"] >= 0.5 else "low")
            
            # 转换合同类型为中文
            cat_parts = rule["cat"].split(",")
            contract_type = "、".join([contract_type_map.get(c, c) for c in cat_parts]) if rule["cat"] != "all" else None
            
            new_rule = RiskRule(
                category_id=category.id,
                name=rule["name"],
                code=rule["id"],
                description=rule["desc"],
                rule_type="keyword",
                rule_config='{"check": "custom"}',
                risk_level=RiskLevel(risk_level),
                risk_score=int(rule["sev"] * 100),
                suggestion=rule["sug"],
                contract_type=contract_type,
                is_active=True,
                created_by=current_user.id,
            )
            db.add(new_rule)
            created_count += 1
    
    # 导入14种毒丸条款检测规则
    for pp in POISON_PILL_PATTERNS:
        result = await db.execute(
            select(RiskRule).where(RiskRule.code == pp["id"])
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            category = categories["all"]
            
            risk_level = "high" if pp["sev"] >= 0.7 else ("medium" if pp["sev"] >= 0.5 else "low")
            
            new_rule = RiskRule(
                category_id=category.id,
                name=pp["name"],
                code=pp["id"],
                description=f"毒丸条款检测 - {pp['type']}型",
                rule_type="regex",
                rule_config='{"pattern": "' + pp["pat"].replace('"', '\\"') + '"}',
                risk_level=RiskLevel(risk_level),
                risk_score=int(pp["sev"] * 100),
                suggestion=f"检测到{pp['type']}型毒丸条款，请审查相关条款",
                contract_type=None,
                is_active=True,
                created_by=current_user.id,
            )
            db.add(new_rule)
            created_count += 1
    
    await db.commit()
    
    return {
        "message": f"成功初始化{created_count}条风险规则",
        "created_count": created_count,
        "industry_rules": len(INDUSTRY_RISK_RULES),
        "poison_pills": len(POISON_PILL_PATTERNS),
    }
