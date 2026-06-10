"""
审查模板服务 - 不同合同类型使用不同审查模板
"""

import json
import logging
from typing import Optional, List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.review import ReviewTemplate

logger = logging.getLogger(__name__)

# 内置审查模板
BUILTIN_TEMPLATES = {
    "procurement": {
        "name": "采购合同审查模板",
        "contract_type": "procurement",
        "description": "适用于设备、原材料等采购合同",
        "checklist": [
            {"item": "供应商资质审查", "category": "合同主体", "required": True},
            {"item": "标的物规格、数量、质量标准", "category": "合同标的", "required": True},
            {"item": "价格条款及价格调整机制", "category": "价款与支付", "required": True},
            {"item": "交货时间、地点、方式", "category": "履行期限", "required": True},
            {"item": "验收标准和验收程序", "category": "合同标的", "required": True},
            {"item": "付款条件和付款方式", "category": "价款与支付", "required": True},
            {"item": "违约责任（迟延交货、质量不合格）", "category": "违约责任", "required": True},
            {"item": "质保期和售后服务", "category": "合同标的", "required": False},
            {"item": "知识产权归属", "category": "知识产权", "required": False},
            {"item": "保密条款", "category": "保密条款", "required": False},
            {"item": "争议解决方式", "category": "争议解决", "required": True},
            {"item": "不可抗力条款", "category": "不可抗力", "required": True},
        ],
        "risk_rules": [
            {"rule": "金额超过50万需提供履约保证金", "severity": "high", "category": "价款与支付"},
            {"rule": "交货期超过90天需分批交付条款", "severity": "medium", "category": "履行期限"},
            {"rule": "质保期不得少于12个月", "severity": "medium", "category": "合同标的"},
            {"rule": "违约金比例不得超过合同金额20%", "severity": "high", "category": "违约责任"},
        ],
        "prompt_suffix": """额外关注：
1. 供应商是否具备相关资质和生产能力
2. 价格是否合理，是否需要比价
3. 付款节奏是否与交付里程碑挂钩
4. 质量标准是否明确，验收程序是否可执行
5. 退换货条款是否合理""",
    },
    "sales": {
        "name": "销售合同审查模板",
        "contract_type": "sales",
        "description": "适用于产品销售合同",
        "checklist": [
            {"item": "买方资信审查", "category": "合同主体", "required": True},
            {"item": "产品规格、数量、单价", "category": "合同标的", "required": True},
            {"item": "交付方式和运费承担", "category": "履行期限", "required": True},
            {"item": "付款条件和账期", "category": "价款与支付", "required": True},
            {"item": "发票开具时间和类型", "category": "价款与支付", "required": True},
            {"item": "退换货条款", "category": "合同标的", "required": True},
            {"item": "违约责任", "category": "违约责任", "required": True},
            {"item": "风险转移（货物毁损灭失）", "category": "合同标的", "required": True},
        ],
        "risk_rules": [
            {"rule": "赊销账期超过90天需提供担保", "severity": "high", "category": "价款与支付"},
            {"rule": "大额订单需买方预付30%", "severity": "medium", "category": "价款与支付"},
        ],
        "prompt_suffix": """额外关注：
1. 买方付款能力和信用状况
2. 账期设置是否合理
3. 风险转移时间点是否明确
4. 退换货条件是否对等""",
    },
    "outsourcing": {
        "name": "外包合同审查模板",
        "contract_type": "outsourcing",
        "description": "适用于软件开发、工程外包等",
        "checklist": [
            {"item": "外包方资质和团队能力", "category": "合同主体", "required": True},
            {"item": "工作范围和交付物定义", "category": "合同标的", "required": True},
            {"item": "项目里程碑和交付时间", "category": "履行期限", "required": True},
            {"item": "验收标准和验收流程", "category": "合同标的", "required": True},
            {"item": "付款与里程碑挂钩", "category": "价款与支付", "required": True},
            {"item": "知识产权归属", "category": "知识产权", "required": True},
            {"item": "保密条款", "category": "保密条款", "required": True},
            {"item": "人员变更条款", "category": "履行期限", "required": False},
            {"item": "违约责任和赔偿上限", "category": "违约责任", "required": True},
        ],
        "risk_rules": [
            {"rule": "知识产权必须明确归属甲方", "severity": "high", "category": "知识产权"},
            {"rule": "源代码必须交付", "severity": "high", "category": "合同标的"},
            {"rule": "赔偿上限不低于合同金额", "severity": "medium", "category": "违约责任"},
        ],
        "prompt_suffix": """额外关注：
1. 工作范围是否清晰，避免范围蔓延
2. 知识产权归属是否明确
3. 源代码交付和质量保证
4. 项目延期的违约责任
5. 人员变更的限制和通知义务""",
    },
    "nda": {
        "name": "保密协议审查模板",
        "contract_type": "nda",
        "description": "适用于保密协议、NDA",
        "checklist": [
            {"item": "保密信息的定义和范围", "category": "保密条款", "required": True},
            {"item": "保密期限", "category": "保密条款", "required": True},
            {"item": "保密义务和例外情形", "category": "保密条款", "required": True},
            {"item": "违约责任和赔偿", "category": "违约责任", "required": True},
            {"item": "信息返还或销毁义务", "category": "保密条款", "required": True},
            {"item": "竞业限制条款（如有）", "category": "其他", "required": False},
        ],
        "risk_rules": [
            {"rule": "保密期限不得超过5年", "severity": "medium", "category": "保密条款"},
            {"rule": "保密范围不得过于宽泛", "severity": "medium", "category": "保密条款"},
        ],
        "prompt_suffix": """额外关注：
1. 保密信息定义是否具体明确
2. 保密期限是否合理
3. 例外情形是否完整（法律要求披露等）
4. 违约赔偿是否可执行""",
    },
    "service": {
        "name": "服务合同审查模板",
        "contract_type": "service",
        "description": "适用于咨询服务、运维服务等",
        "checklist": [
            {"item": "服务内容和范围", "category": "合同标的", "required": True},
            {"item": "服务标准和SLA", "category": "合同标的", "required": True},
            {"item": "服务期限", "category": "履行期限", "required": True},
            {"item": "服务费用和支付方式", "category": "价款与支付", "required": True},
            {"item": "服务人员资质要求", "category": "合同主体", "required": False},
            {"item": "变更和终止条款", "category": "其他", "required": True},
            {"item": "违约责任", "category": "违约责任", "required": True},
        ],
        "risk_rules": [
            {"rule": "SLA指标必须量化", "severity": "high", "category": "合同标的"},
            {"rule": "服务费需与SLA挂钩", "severity": "medium", "category": "价款与支付"},
        ],
        "prompt_suffix": """额外关注：
1. 服务范围是否清晰，避免无限责任
2. SLA指标是否可量化、可衡量
3. 服务变更的流程和费用
4. 知识产权和成果归属""",
    },
    "lease": {
        "name": "租赁合同审查模板",
        "contract_type": "lease",
        "description": "适用于设备租赁、房屋租赁等",
        "checklist": [
            {"item": "租赁物描述和现状", "category": "合同标的", "required": True},
            {"item": "租赁期限", "category": "履行期限", "required": True},
            {"item": "租金及支付方式", "category": "价款与支付", "required": True},
            {"item": "押金和退还条件", "category": "价款与支付", "required": True},
            {"item": "维修保养责任", "category": "合同标的", "required": True},
            {"item": "续租和退租条款", "category": "其他", "required": True},
            {"item": "违约责任", "category": "违约责任", "required": True},
        ],
        "risk_rules": [
            {"rule": "租赁期限不得超过20年", "severity": "high", "category": "履行期限"},
            {"rule": "押金不得超过两个月租金", "severity": "medium", "category": "价款与支付"},
        ],
        "prompt_suffix": """额外关注：
1. 租赁物现状是否明确
2. 维修责任划分是否清晰
3. 提前退租的违约责任
4. 续租优先权""",
    },
    "other": {
        "name": "通用合同审查模板",
        "contract_type": "other",
        "description": "适用于其他类型合同",
        "checklist": [
            {"item": "合同主体信息完整性", "category": "合同主体", "required": True},
            {"item": "合同标的清晰性", "category": "合同标的", "required": True},
            {"item": "价款和支付条款", "category": "价款与支付", "required": True},
            {"item": "履行期限和方式", "category": "履行期限", "required": True},
            {"item": "违约责任", "category": "违约责任", "required": True},
            {"item": "争议解决", "category": "争议解决", "required": True},
        ],
        "risk_rules": [],
        "prompt_suffix": "请进行全面的合同风险审查。",
    },
}


async def get_template_for_contract(
    db: AsyncSession,
    contract_type: str,
) -> dict:
    """获取合同类型的审查模板"""
    # 先查数据库自定义模板
    result = await db.execute(
        select(ReviewTemplate)
        .where(ReviewTemplate.contract_type == contract_type)
        .where(ReviewTemplate.is_active == True)
    )
    custom_template = result.scalar_one_or_none()
    
    if custom_template:
        return {
            "id": custom_template.id,
            "name": custom_template.name,
            "contract_type": custom_template.contract_type,
            "description": custom_template.description,
            "checklist": json.loads(custom_template.checklist) if custom_template.checklist else [],
            "risk_rules": json.loads(custom_template.risk_rules) if custom_template.risk_rules else [],
            "prompt_suffix": "",
            "is_custom": True,
        }
    
    # 使用内置模板
    template = BUILTIN_TEMPLATES.get(contract_type, BUILTIN_TEMPLATES["other"])
    return {
        "id": None,
        **template,
        "is_custom": False,
    }


async def list_templates(db: AsyncSession) -> List[dict]:
    """列出所有模板（内置 + 自定义）"""
    templates = []
    
    # 内置模板
    for key, tpl in BUILTIN_TEMPLATES.items():
        templates.append({
            "id": None,
            "contract_type": key,
            "name": tpl["name"],
            "description": tpl["description"],
            "is_custom": False,
            "is_active": True,
        })
    
    # 自定义模板
    result = await db.execute(select(ReviewTemplate).where(ReviewTemplate.is_active == True))
    custom_templates = result.scalars().all()
    for tpl in custom_templates:
        templates.append({
            "id": tpl.id,
            "contract_type": tpl.contract_type,
            "name": tpl.name,
            "description": tpl.description,
            "is_custom": True,
            "is_active": tpl.is_active,
        })
    
    return templates
