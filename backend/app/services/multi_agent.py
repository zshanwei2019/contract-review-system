"""
多Agent协作服务 - 法务/财务/业务多视角审查
"""

import json
import logging
from typing import Optional, List, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import AgentMessage, ReviewCase
from app.models.contract import Contract
from app.services.ai_review import review_contract_with_ai, extract_file_content

logger = logging.getLogger(__name__)

# Agent角色定义
AGENT_ROLES = {
    "legal": {
        "name": "法务审查Agent",
        "icon": "⚖️",
        "focus": "法律风险、合同条款合规性、违约责任、争议解决",
        "system_prompt": """你是一位资深企业法务顾问，专注于法律风险审查。
重点关注：
1. 合同条款是否符合《民法典》《合同法》等法律规定
2. 违约责任条款是否对等、可执行
3. 争议解决条款是否有利于我方
4. 知识产权归属是否明确
5. 保密条款是否充分保护我方利益
6. 不可抗力条款是否合理
7. 合同终止和解除条件

输出JSON格式，包含 findings 列表。""",
    },
    "finance": {
        "name": "财务审查Agent",
        "icon": "💰",
        "focus": "金额合理性、支付条件、税务条款、发票要求",
        "system_prompt": """你是一位企业财务顾问，专注于财务风险审查。
重点关注：
1. 合同金额是否在预算范围内
2. 付款条件是否合理（账期、分期、预付款比例）
3. 发票条款是否明确（类型、税率、开票时间）
4. 税费承担是否清晰
5. 价格调整机制是否合理
6. 违约金和赔偿金额是否过高
7. 资金安全风险

输出JSON格式，包含 findings 列表。""",
    },
    "business": {
        "name": "业务审查Agent",
        "icon": "📋",
        "focus": "业务可行性、交付条件、质量标准、合作关系",
        "system_prompt": """你是一位业务部门负责人，专注于业务可行性审查。
重点关注：
1. 合同标的是否满足业务需求
2. 交付时间是否可行，是否与项目计划匹配
3. 质量标准是否明确、可验证
4. 验收流程是否合理
5. 供应商/合作方能力是否匹配
6. 售后服务和质保条款
7. 对业务连续性的影响

输出JSON格式，包含 findings 列表。""",
    },
}


async def run_multi_agent_review(
    db: AsyncSession,
    contract: Contract,
    agents: Optional[List[str]] = None,
    file_content: Optional[str] = None,
) -> Dict[str, dict]:
    """
    运行多Agent审查
    返回各Agent的审查结果
    """
    if agents is None:
        agents = ["legal", "finance", "business"]

    # 提取文件内容
    if file_content is None and contract.file_path:
        file_content = await extract_file_content(contract.file_path)

    contract_data = {
        "title": contract.title,
        "contract_type": contract.contract_type.value if contract.contract_type else "",
        "party_a": contract.party_a,
        "party_b": contract.party_b,
        "amount": str(contract.amount) if contract.amount else None,
        "currency": contract.currency,
        "sign_date": contract.sign_date.strftime("%Y-%m-%d") if contract.sign_date else None,
        "effective_date": contract.effective_date.strftime("%Y-%m-%d") if contract.effective_date else None,
        "expiry_date": contract.expiry_date.strftime("%Y-%m-%d") if contract.expiry_date else None,
        "description": contract.description,
        "key_terms": contract.key_terms,
        "special_terms": contract.special_terms,
        "file_path": contract.file_path,
    }

    results = {}
    for agent_id in agents:
        if agent_id not in AGENT_ROLES:
            continue

        agent = AGENT_ROLES[agent_id]
        logger.info(f"运行{agent['name']}审查: contract_id={contract.id}")

        # 使用Agent专用prompt
        agent_result = await review_contract_with_ai(
            contract_data,
            file_content,
            system_prompt_override=agent["system_prompt"],
        )

        results[agent_id] = {
            "agent_name": agent["name"],
            "icon": agent["icon"],
            "focus": agent["focus"],
            **agent_result,
        }

    return results


async def save_agent_messages(
    db: AsyncSession,
    review_case_id: int,
    agent_results: Dict[str, dict],
):
    """保存Agent间通信记录"""
    for agent_id, result in agent_results.items():
        for finding in result.get("findings", []):
            msg = AgentMessage(
                review_case_id=review_case_id,
                from_agent=agent_id,
                to_agent=None,  # 广播
                message_type="finding",
                content=json.dumps(finding, ensure_ascii=False),
            )
            db.add(msg)

    await db.commit()


async def merge_agent_results(agent_results: Dict[str, dict]) -> dict:
    """合并多Agent审查结果"""
    all_findings = []
    risk_scores = []

    for agent_id, result in agent_results.items():
        agent_name = AGENT_ROLES.get(agent_id, {}).get("name", agent_id)
        risk_scores.append(result.get("risk_score", 50))

        for finding in result.get("findings", []):
            finding["agent_source"] = agent_id
            finding["agent_name"] = agent_name
            all_findings.append(finding)

    # 计算综合风险评分（加权平均）
    avg_score = sum(risk_scores) / len(risk_scores) if risk_scores else 50

    # 确定综合风险等级
    high_count = sum(1 for f in all_findings if f.get("risk_level") == "high")
    medium_count = sum(1 for f in all_findings if f.get("risk_level") == "medium")

    if high_count > 0:
        risk_level = "high"
    elif medium_count > 2:
        risk_level = "medium"
    else:
        risk_level = "low"

    # 按类别分组
    by_category = {}
    for f in all_findings:
        cat = f.get("category", "其他")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(f)

    # 生成综合摘要
    summary_parts = []
    for agent_id, result in agent_results.items():
        agent_icon = AGENT_ROLES.get(agent_id, {}).get("icon", "")
        summary_parts.append(f"{agent_icon} {result.get('summary', '无摘要')}")

    return {
        "risk_level": risk_level,
        "risk_score": round(avg_score),
        "summary": " | ".join(summary_parts),
        "total_findings": len(all_findings),
        "by_category": by_category,
        "agent_results": agent_results,
    }
