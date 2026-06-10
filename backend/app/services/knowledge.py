"""
领域知识库服务 - 法规条文检索 + 企业合规规则
"""

import json
import logging
from typing import Optional, List, Dict
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.memory import ContractKnowledge, KnowledgeType

logger = logging.getLogger(__name__)

# 内置法律法规知识库
BUILTIN_LAWS = [
    {
        "title": "民法典·合同编·通则",
        "contract_type": "all",
        "knowledge_type": "law",
        "content": """【合同成立】第四百九十条：当事人采用合同书形式订立合同的，自当事人均签名、盖章或者按指印时合同成立。
【合同生效】第五百零二条：依法成立的合同，自成立时生效，但是法律另有规定或者当事人另有约定的除外。
【格式条款】第四百九十六条：提供格式条款的一方未履行提示或者说明义务，致使对方没有注意或者理解与其有重大利害关系的条款的，对方可以主张该条款不成为合同的内容。
【违约责任】第五百七十七条：当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。
【违约金】第五百八十五条：约定的违约金低于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以增加；约定的违约金过分高于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以适当减少。""",
    },
    {
        "title": "民法典·合同编·买卖合同",
        "contract_type": "procurement,sales",
        "knowledge_type": "law",
        "content": """【标的物风险转移】第六百零四条：标的物毁损、灭失的风险，在标的物交付之前由出卖人承担，交付之后由买受人承担。
【质量保证】第六百一十七条：出卖人交付的标的物不符合质量要求的，买受人可以依据本法第五百八十二条至第五百八十四条的规定请求承担违约责任。
【检验期间】第六百二十一条：当事人约定检验期限的，买受人应当在检验期限内将标的物的数量或者质量不符合约定的情形通知出卖人。""",
    },
    {
        "title": "劳动合同法要点",
        "contract_type": "labor",
        "knowledge_type": "law",
        "content": """【试用期】第十九条：劳动合同期限三个月以上不满一年的，试用期不得超过一个月；劳动合同期限一年以上不满三年的，试用期不得超过二个月；三年以上固定期限和无固定期限的劳动合同，试用期不得超过六个月。
【竞业限制】第二十四条：竞业限制的人员限于用人单位的高级管理人员、高级技术人员和其他负有保密义务的人员。竞业限制期限不得超过二年。
【经济补偿】第四十七条：经济补偿按劳动者在本单位工作的年限，每满一年支付一个月工资的标准向劳动者支付。""",
    },
    {
        "title": "保密协议法律要点",
        "contract_type": "nda",
        "knowledge_type": "law",
        "content": """【商业秘密定义】反不正当竞争法第九条：本法所称的商业秘密，是指不为公众所知悉、具有商业价值并经权利人采取相应保密措施的技术信息、经营信息等商业信息。
【保密义务】保密义务可以约定保密期限，但不得违反法律强制性规定。一般建议保密期限不超过5年。
【竞业限制补偿】用人单位与劳动者约定竞业限制的，在竞业限制期限内需按月给予劳动者经济补偿。""",
    },
    {
        "title": "租赁合同法律要点",
        "contract_type": "lease",
        "knowledge_type": "law",
        "content": """【租赁期限】第七百零五条：租赁期限不得超过二十年。超过二十年的，超过部分无效。
【买卖不破租赁】第七百二十五条：租赁物在承租人按照租赁合同占有期限内发生所有权变动的，不影响租赁合同的效力。
【优先购买权】第七百二十六条：出租人出卖租赁房屋的，应当在出卖之前的合理期限内通知承租人，承租人享有以同等条件优先购买的权利。""",
    },
]

# 企业合规规则
BUILTIN_COMPLIANCE_RULES = [
    {
        "title": "大额合同审批规则",
        "contract_type": "all",
        "knowledge_type": "regulation",
        "content": """金额等级与审批权限：
- 10万以下：部门经理审批
- 10-50万：分管副总审批
- 50-100万：总经理审批
- 100万以上：董事会审批

大额合同要求：
- 必须提供对方资信证明
- 必须进行法律审查
- 必须提供履约保证金或银行保函
- 必须签订书面合同""",
    },
    {
        "title": "供应商合同管理规范",
        "contract_type": "procurement",
        "knowledge_type": "regulation",
        "content": """供应商准入要求：
- 注册资本不低于合同金额的30%
- 成立时间不少于2年
- 无重大诉讼和行政处罚记录
- 具备相关行业资质

合同签订要求：
- 采购金额超过5万必须签订书面合同
- 付款条件：预付不超过30%，验收后付尾款
- 质保期不少于12个月
- 违约金不低于合同金额的5%""",
    },
    {
        "title": "合同风险分级标准",
        "contract_type": "all",
        "knowledge_type": "regulation",
        "content": """风险等级划分：
- 高风险：金额>100万、新供应商、首次合作、特殊条款
- 中风险：金额50-100万、已有供应商、标准条款
- 低风险：金额<50万、长期合作供应商、标准模板

各级风险审查要求：
- 高风险：法务+财务+业务三方会审
- 中风险：法务+业务双审
- 低风险：业务自审，法务抽检""",
    },
]


async def init_builtin_knowledge(db: AsyncSession):
    """初始化内置知识库"""
    all_knowledge = BUILTIN_LAWS + BUILTIN_COMPLIANCE_RULES

    for item in all_knowledge:
        # 检查是否已存在
        result = await db.execute(
            select(ContractKnowledge)
            .where(ContractKnowledge.title == item["title"])
            .where(ContractKnowledge.knowledge_type == item["knowledge_type"])
        )
        existing = result.scalar_one_or_none()

        if not existing:
            knowledge = ContractKnowledge(
                contract_type=item["contract_type"],
                knowledge_type=item["knowledge_type"],
                title=item["title"],
                content=item["content"],
                source="builtin",
            )
            db.add(knowledge)

    await db.commit()
    logger.info("内置知识库初始化完成")


async def search_laws_for_contract(
    db: AsyncSession,
    contract_type: str,
) -> List[dict]:
    """搜索适用于合同类型的法律法规"""
    result = await db.execute(
        select(ContractKnowledge)
        .where(
            (ContractKnowledge.knowledge_type == KnowledgeType.LAW) |
            (ContractKnowledge.knowledge_type == KnowledgeType.REGULATION)
        )
        .where(
            (ContractKnowledge.contract_type == "all") |
            (ContractKnowledge.contract_type.contains(contract_type))
        )
        .order_by(ContractKnowledge.usefulness_score.desc())
    )
    items = result.scalars().all()

    return [
        {
            "id": item.id,
            "title": item.title,
            "type": item.knowledge_type.value,
            "content": item.content,
            "source": item.source,
        }
        for item in items
    ]


async def get_compliance_rules(
    db: AsyncSession,
    contract_type: str,
) -> List[dict]:
    """获取企业合规规则"""
    result = await db.execute(
        select(ContractKnowledge)
        .where(ContractKnowledge.knowledge_type == KnowledgeType.REGULATION)
        .where(
            (ContractKnowledge.contract_type == "all") |
            (ContractKnowledge.contract_type.contains(contract_type))
        )
    )
    items = result.scalars().all()

    return [
        {
            "id": item.id,
            "title": item.title,
            "content": item.content,
        }
        for item in items
    ]
