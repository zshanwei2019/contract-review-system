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
# 初始化默认风险规则
# ============================================================
INIT_RISK_CATEGORIES = [
  {
    "code": "FINANCIAL",
    "name": "财务风险",
    "icon": "Money",
    "color": "#F56C6C",
    "description": "付款、价款、税务等财务相关风险",
    "sort_order": 1
  },
  {
    "code": "BREACH",
    "name": "违约风险",
    "icon": "Warning",
    "color": "#E6A23C",
    "description": "违约金、赔偿、履约等风险",
    "sort_order": 2
  },
  {
    "code": "COMPLIANCE",
    "name": "合规风险",
    "icon": "Lock",
    "color": "#909399",
    "description": "法律法规、行业标准合规风险",
    "sort_order": 3
  },
  {
    "code": "IP",
    "name": "知识产权",
    "icon": "Document",
    "color": "#67C23A",
    "description": "知识产权归属、侵权风险",
    "sort_order": 4
  },
  {
    "code": "CONFIDENTIALITY",
    "name": "保密风险",
    "icon": "View",
    "color": "#409EFF",
    "description": "商业秘密、保密条款风险",
    "sort_order": 5
  },
  {
    "code": "TERMINATION",
    "name": "解除终止",
    "icon": "CircleClose",
    "color": "#F78989",
    "description": "合同解除、终止条件风险",
    "sort_order": 6
  },
  {
    "code": "LIABILITY",
    "name": "责任承担",
    "icon": "User",
    "color": "#9B59B6",
    "description": "责任划分、连带风险",
    "sort_order": 7
  },
  {
    "code": "FORCE_MAJEURE",
    "name": "不可抗力",
    "icon": "Lightning",
    "color": "#1ABC9C",
    "description": "不可抗力界定与后果",
    "sort_order": 8
  }
]

INIT_RISK_RULES = [
  {
    "category": "FINANCIAL",
    "code": "FIN-001",
    "name": "付款周期过长",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"验收后 90 天付款\",\"90 日\",\"3 个月付款\"]}",
    "risk_level": "high",
    "risk_score": 70,
    "description": "付款周期超过 60 天,资金占用风险高",
    "suggestion": "建议缩短付款周期至 30-45 天,并约定分期付款节点",
    "legal_basis": "《合同法》第六十条 全面履行原则"
  },
  {
    "category": "FINANCIAL",
    "code": "FIN-002",
    "name": "未约定付款方式",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"付款方式\",\"支付方式\"]}",
    "risk_level": "medium",
    "risk_score": 50,
    "description": "合同未明确约定具体付款方式",
    "suggestion": "建议明确付款方式,如银行转账,并注明收款账户信息",
    "legal_basis": "《民法典》第五百零九条"
  },
  {
    "category": "BREACH",
    "code": "BRE-001",
    "name": "违约金比例过高",
    "rule_type": "regex",
    "rule_config": "{\"pattern\":\"违约金.{0,10}(30%|40%|50%)\"}",
    "risk_level": "high",
    "risk_score": 75,
    "description": "违约金比例超过合同总金额 30%",
    "suggestion": "建议违约金比例控制在 20-30% 以内",
    "legal_basis": "《民法典》第五百八十五条 违约金约定"
  },
  {
    "category": "BREACH",
    "code": "BRE-002",
    "name": "未约定逾期利息",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"逾期\",\"违约金\"]}",
    "risk_level": "medium",
    "risk_score": 55,
    "description": "未约定逾期付款利息或计算方式",
    "suggestion": "建议约定逾期利息按 LPR 计算",
    "legal_basis": "最高人民法院司法解释"
  },
  {
    "category": "COMPLIANCE",
    "code": "COM-001",
    "name": "合同主体资质不全",
    "rule_type": "keyword",
    "rule_config": "{\"required\":[\"营业执照\",\"资质证书\"]}",
    "risk_level": "high",
    "risk_score": 80,
    "description": "未审查对方营业执照及行业资质",
    "suggestion": "签约前审查营业执照、资质证书原件并保留复印件",
    "legal_basis": "《民法典》第一百四十三条"
  },
  {
    "category": "COMPLIANCE",
    "code": "COM-002",
    "name": "管辖法院约定不利",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"原告住所地\",\"甲方所在地\"]}",
    "risk_level": "low",
    "risk_score": 30,
    "description": "约定由原告住所地或甲方所在地管辖",
    "suggestion": "建议约定由我方所在地或合同签订地法院管辖",
    "legal_basis": "《民事诉讼法》第三十五条"
  },
  {
    "category": "IP",
    "code": "IP-001",
    "name": "知识产权归属不清",
    "rule_type": "keyword",
    "rule_config": "{\"required\":[\"知识产权\",\"归属\"]}",
    "risk_level": "high",
    "risk_score": 75,
    "description": "未明确约定合同产生的知识产权归属",
    "suggestion": "建议明确约定知识产权归哪方所有,以及使用许可范围",
    "legal_basis": "《民法典》第八百四十七条"
  },
  {
    "category": "IP",
    "code": "IP-002",
    "name": "侵权责任未约定",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"侵权\",\"责任\"]}",
    "risk_level": "medium",
    "risk_score": 50,
    "description": "未约定第三方侵权时双方的责任承担方式",
    "suggestion": "建议约定一方原因导致侵权的由该方承担全部责任",
    "legal_basis": "《民法典》第一千一百六十八条"
  },
  {
    "category": "CONFIDENTIALITY",
    "code": "CON-001",
    "name": "保密期限不足",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"保密期限\",\"保密期\"]}",
    "risk_level": "medium",
    "risk_score": 55,
    "description": "保密期限不足 2 年,无法有效保护商业秘密",
    "suggestion": "建议保密期限不少于 3-5 年,核心商业秘密永久保密",
    "legal_basis": "《反不正当竞争法》第九条"
  },
  {
    "category": "CONFIDENTIALITY",
    "code": "CON-002",
    "name": "保密范围过窄",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"保密信息\",\"商业秘密\"]}",
    "risk_level": "medium",
    "risk_score": 50,
    "description": "保密信息定义范围过窄,可能遗漏重要信息",
    "suggestion": "建议扩大保密信息范围,包括技术、经营、财务、人事等",
    "legal_basis": "《反不正当竞争法》第九条"
  },
  {
    "category": "TERMINATION",
    "code": "TER-001",
    "name": "解除条件过严",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"解除合同\",\"解除条件\"]}",
    "risk_level": "medium",
    "risk_score": 50,
    "description": "解除条件约定过严,一旦对方违约难以解除",
    "suggestion": "建议约定对方违约 30 日内未改正的,我方有权解除",
    "legal_basis": "《民法典》第五百六十三条"
  },
  {
    "category": "TERMINATION",
    "code": "TER-002",
    "name": "未约定合同终止后果",
    "rule_type": "keyword",
    "rule_config": "{\"required\":[\"终止\",\"结算\"]}",
    "risk_level": "low",
    "risk_score": 35,
    "description": "未约定合同终止后的结算、交接等善后事宜",
    "suggestion": "建议明确终止后的款项结算、资料交接、保密义务延续等",
    "legal_basis": "《民法典》第五百六十六条"
  },
  {
    "category": "LIABILITY",
    "code": "LIA-001",
    "name": "责任划分不明确",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"责任\",\"承担\"]}",
    "risk_level": "medium",
    "risk_score": 50,
    "description": "双方责任划分不明确,易产生纠纷",
    "suggestion": "建议分项列明双方责任,以及违约责任的具体承担方式",
    "legal_basis": "《民法典》第五百零九条"
  },
  {
    "category": "LIABILITY",
    "code": "LIA-002",
    "name": "连带责任约定",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"连带责任\",\"担保\"]}",
    "risk_level": "high",
    "risk_score": 70,
    "description": "存在连带责任约定,加重我方责任",
    "suggestion": "建议要求提供反担保,或明确连带责任的承担上限",
    "legal_basis": "《民法典》第五百一十八条"
  },
  {
    "category": "FORCE_MAJEURE",
    "code": "FMA-001",
    "name": "不可抗力范围过窄",
    "rule_type": "keyword",
    "rule_config": "{\"keywords\":[\"不可抗力\",\"自然灾害\"]}",
    "risk_level": "medium",
    "risk_score": 45,
    "description": "不可抗力范围过窄,可能不包含疫情、政策变化等",
    "suggestion": "建议参照《民法典》第一百八十条规定,扩大不可抗力范围",
    "legal_basis": "《民法典》第一百八十条"
  },
  {
    "category": "FORCE_MAJEURE",
    "code": "FMA-002",
    "name": "未约定通知义务",
    "rule_type": "keyword",
    "rule_config": "{\"required\":[\"通知\",\"证明\"]}",
    "risk_level": "low",
    "risk_score": 30,
    "description": "未约定不可抗力发生后的通知义务和证明义务",
    "suggestion": "建议约定不可抗力发生后 3 日内通知对方并提供证明",
    "legal_basis": "《民法典》第五百九十条"
  }
]


@router.post("/rules/init", response_model=dict)
async def init_default_risk_rules(
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """初始化默认风险分类和规则 (幂等, 已存在则跳过)"""
    # 1. 检查分类
    cat_result = await db.execute(select(RiskCategory))
    existing_cats = {c.code: c for c in cat_result.scalars().all()}

    cat_code_to_id = {}
    for cat_data in INIT_RISK_CATEGORIES:
        if cat_data["code"] in existing_cats:
            cat_code_to_id[cat_data["code"]] = existing_cats[cat_data["code"]].id
            continue
        cat = RiskCategory(**cat_data)
        db.add(cat)
        await db.flush()
        cat_code_to_id[cat_data["code"]] = cat.id

    # 2. 检查规则
    rule_result = await db.execute(select(RiskRule.code))
    existing_rule_codes = {r[0] for r in rule_result.all()}

    created_count = 0
    skipped_count = 0
    for rule_data in INIT_RISK_RULES:
        if rule_data["code"] in existing_rule_codes:
            skipped_count += 1
            continue
        category_code = rule_data.pop("category")
        rule = RiskRule(
            **rule_data,
            category_id=cat_code_to_id[category_code],
            created_by=current_user.id,
        )
        db.add(rule)
        created_count += 1

    await db.commit()

    return {
        "categories_total": len(INIT_RISK_CATEGORIES),
        "rules_created": created_count,
        "rules_skipped": skipped_count,
        "message": f"初始化完成: 新建 {created_count} 条规则, 跳过 {skipped_count} 条已存在规则",
    }
