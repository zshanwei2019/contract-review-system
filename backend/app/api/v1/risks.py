from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.risk import RiskRule, RiskCategory, RiskItem, RiskLevel
from app.schemas.risk import (
    RiskRuleCreate, RiskRuleUpdate, RiskRuleResponse, RiskRuleList,
    RiskCategoryCreate, RiskCategoryResponse,
    RiskItemCreate, RiskItemUpdate, RiskItemResponse, RiskItemList,
    RiskQuantificationRequest, RiskQuantificationResponse, ContractRiskSummary,
)
from app.services.risk_quantification import (
    calculate_risk_score, determine_risk_level, calculate_expected_loss,
    generate_quantification_detail, estimate_financial_impact,
)

router = APIRouter()


@router.get("/categories", response_model=list[RiskCategoryResponse])
async def list_risk_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RiskCategory).where(RiskCategory.is_active == True).order_by(RiskCategory.sort_order)
    )
    return result.scalars().all()


@router.post("/categories", response_model=RiskCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_risk_category(
    category_data: RiskCategoryCreate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    category = RiskCategory(**category_data.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


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
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
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
    rule = RiskRule(**rule_data.model_dump(), created_by=current_user.id)
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风险规则不存在")
    
    update_data = rule_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule


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
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    query = query.order_by(RiskItem.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return RiskItemList(total=total, items=items)


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风险项不存在")
    
    update_data = item_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    if item_data.is_resolved:
        item.resolved_by = current_user.id
        item.resolved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(item)
    return item


# === 风险量化评估 API ===

@router.post("/items/{item_id}/quantify", response_model=RiskItemResponse)
async def quantify_risk_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    对风险项进行量化评估
    自动计算四维评分、综合评分、财务影响
    """
    result = await db.execute(select(RiskItem).where(RiskItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风险项不存在")
    
    # 获取关联规则的权重配置
    weights = None
    if item.rule_id:
        rule_result = await db.execute(select(RiskRule).where(RiskRule.id == item.rule_id))
        rule = rule_result.scalar_one_or_none()
        if rule:
            weights = {
                "severity": rule.weight_severity or 0.40,
                "likelihood": rule.weight_likelihood or 0.25,
                "financial": rule.weight_financial or 0.20,
                "responsibility": rule.weight_responsibility or 0.15,
            }
    
    # 如果已有四维评分，直接计算
    if item.score_severity is not None:
        risk_score = calculate_risk_score(
            item.score_severity, item.score_likelihood or 0,
            item.score_financial or 0, item.score_responsibility or 0,
            weights,
        )
        item.risk_score = risk_score
        item.risk_level = RiskLevel(determine_risk_level(risk_score))
        
        # 计算期望损失
        if item.potential_loss_max and item.loss_probability:
            item.expected_loss = calculate_expected_loss(item.potential_loss_max, item.loss_probability)
        
        # 生成量化详情
        item.quantification_detail = generate_quantification_detail(
            item.score_severity, item.score_likelihood or 0,
            item.score_financial or 0, item.score_responsibility or 0,
            risk_score, weights,
        )
    else:
        # 如果没有评分，基于风险等级进行基础估算
        level = item.risk_level.value if hasattr(item.risk_level, 'value') else item.risk_level
        
        # 基础评分映射
        base_scores = {
            "high": {"severity": 80, "likelihood": 70, "financial": 75, "responsibility": 65},
            "medium": {"severity": 55, "likelihood": 45, "financial": 50, "responsibility": 40},
            "low": {"severity": 25, "likelihood": 20, "financial": 20, "responsibility": 15},
            "none": {"severity": 5, "likelihood": 5, "financial": 5, "responsibility": 5},
        }
        scores = base_scores.get(level, base_scores["low"])
        item.score_severity = scores["severity"]
        item.score_likelihood = scores["likelihood"]
        item.score_financial = scores["financial"]
        item.score_responsibility = scores["responsibility"]
        
        risk_score = calculate_risk_score(
            scores["severity"], scores["likelihood"],
            scores["financial"], scores["responsibility"],
            weights,
        )
        item.risk_score = risk_score
        
        # 估算财务影响
        fin_impact = estimate_financial_impact(level)
        item.potential_loss_min = fin_impact["potential_loss_min"]
        item.potential_loss_max = fin_impact["potential_loss_max"]
        item.loss_probability = fin_impact["loss_probability"]
        item.expected_loss = calculate_expected_loss(
            fin_impact["potential_loss_max"], fin_impact["loss_probability"]
        )
        
        item.quantification_detail = generate_quantification_detail(
            scores["severity"], scores["likelihood"],
            scores["financial"], scores["responsibility"],
            risk_score, weights,
        )
    
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/contracts/{contract_id}/risk-summary", response_model=ContractRiskSummary)
async def get_contract_risk_summary(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取合同风险汇总"""
    result = await db.execute(
        select(RiskItem).where(RiskItem.contract_id == contract_id)
    )
    items = result.scalars().all()
    
    high_count = sum(1 for i in items if i.risk_level == RiskLevel.HIGH)
    medium_count = sum(1 for i in items if i.risk_level == RiskLevel.MEDIUM)
    low_count = sum(1 for i in items if i.risk_level == RiskLevel.LOW)
    
    # 计算合同综合风险评分
    if items:
        scores = [i.risk_score for i in items if i.risk_score is not None]
        overall_score = max(scores) if scores else 0
        total_expected_loss = sum(i.expected_loss or 0 for i in items)
    else:
        overall_score = 0
        total_expected_loss = 0
    
    overall_level = determine_risk_level(overall_score)
    
    return ContractRiskSummary(
        contract_id=contract_id,
        total_risks=len(items),
        high_risks=high_count,
        medium_risks=medium_count,
        low_risks=low_count,
        overall_score=overall_score,
        overall_level=overall_level,
        total_expected_loss=total_expected_loss,
        risk_items=items,
    )


@router.post("/contracts/{contract_id}/quantify-all")
async def quantify_all_risks(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量量化合同下所有风险项"""
    result = await db.execute(
        select(RiskItem).where(RiskItem.contract_id == contract_id)
    )
    items = result.scalars().all()
    
    if not items:
        raise HTTPException(status_code=404, detail="该合同无风险项")
    
    quantified = []
    for item in items:
        # 复用单个量化逻辑
        level = item.risk_level.value if hasattr(item.risk_level, 'value') else item.risk_level
        base_scores = {
            "high": {"severity": 80, "likelihood": 70, "financial": 75, "responsibility": 65},
            "medium": {"severity": 55, "likelihood": 45, "financial": 50, "responsibility": 40},
            "low": {"severity": 25, "likelihood": 20, "financial": 20, "responsibility": 15},
            "none": {"severity": 5, "likelihood": 5, "financial": 5, "responsibility": 5},
        }
        scores = base_scores.get(level, base_scores["low"])
        
        if item.score_severity is None:
            item.score_severity = scores["severity"]
            item.score_likelihood = scores["likelihood"]
            item.score_financial = scores["financial"]
            item.score_responsibility = scores["responsibility"]
        
        weights = None
        if item.rule_id:
            rule_result = await db.execute(select(RiskRule).where(RiskRule.id == item.rule_id))
            rule = rule_result.scalar_one_or_none()
            if rule:
                weights = {
                    "severity": rule.weight_severity or 0.40,
                    "likelihood": rule.weight_likelihood or 0.25,
                    "financial": rule.weight_financial or 0.20,
                    "responsibility": rule.weight_responsibility or 0.15,
                }
        
        risk_score = calculate_risk_score(
            item.score_severity, item.score_likelihood or 0,
            item.score_financial or 0, item.score_responsibility or 0,
            weights,
        )
        item.risk_score = risk_score
        
        if item.potential_loss_max and item.loss_probability:
            item.expected_loss = calculate_expected_loss(item.potential_loss_max, item.loss_probability)
        else:
            fin_impact = estimate_financial_impact(level)
            item.potential_loss_min = fin_impact["potential_loss_min"]
            item.potential_loss_max = fin_impact["potential_loss_max"]
            item.loss_probability = fin_impact["loss_probability"]
            item.expected_loss = calculate_expected_loss(
                fin_impact["potential_loss_max"], fin_impact["loss_probability"]
            )
        
        item.quantification_detail = generate_quantification_detail(
            item.score_severity, item.score_likelihood or 0,
            item.score_financial or 0, item.score_responsibility or 0,
            risk_score, weights,
        )
        quantified.append(item)
    
    await db.commit()
    
    return {
        "contract_id": contract_id,
        "quantified_count": len(quantified),
        "message": f"已量化 {len(quantified)} 个风险项",
    }




# ============================================================
# 初始化23条行业风控规则和14种毒丸条款 (远端 9202117 设计)
# ============================================================
@router.post("/init-rules")
async def init_risk_rules(
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """初始化23条行业风控规则和14种毒丸条款检测规则 (幂等)"""
    from app.services.risk_rules_engine import INDUSTRY_RISK_RULES, POISON_PILL_PATTERNS

    created_count = 0
    skipped_count = 0

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

        if existing:
            skipped_count += 1
            continue
        cat_code = rule["cat"].split(",")[0] if rule["cat"] != "all" else "all"
        category = categories.get(cat_code, categories["all"])

        risk_level = "high" if rule["sev"] >= 0.7 else ("medium" if rule["sev"] >= 0.5 else "low")

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
            contract_type=rule["cat"] if rule["cat"] != "all" else None,
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

        if existing:
            skipped_count += 1
            continue
        category = categories["all"]

        risk_level = "high" if pp["sev"] >= 0.7 else ("medium" if pp["sev"] >= 0.5 else "low")

        new_rule = RiskRule(
            category_id=category.id,
            name=pp["name"],
            code=pp["id"],
            description=f"毒丸条款检测 - {pp['type']}型",
            rule_type="regex",
            rule_config='{"pattern": "' + pp["pat"].replace('"', '\"') + '"}',
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
        "skipped_count": skipped_count,
        "industry_rules": len(INDUSTRY_RISK_RULES),
        "poison_pills": len(POISON_PILL_PATTERNS),
    }
