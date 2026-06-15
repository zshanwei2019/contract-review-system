"""
5-Agent协作审查架构
法律合规 / 财务风险 / 商务条件 / 风控规则 / 知识图谱
五维加权评分模型
"""

import json
import logging
from typing import Optional, List, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import AgentMessage, ReviewCase
from app.models.contract import Contract
from app.services.ai_review import review_contract_with_ai, extract_file_content
from app.services.risk_rules_engine import full_risk_analysis, check_industry_risks, detect_poison_pills

logger = logging.getLogger(__name__)

# 五维权重
AGENT_WEIGHTS = {
    "legal": 0.30,
    "finance": 0.20,
    "business": 0.15,
    "risk_rules": 0.20,
    "knowledge": 0.15,
}

# Agent角色定义（5个Agent）
AGENT_ROLES = {
    "legal": {
        "name": "法律合规Agent",
        "icon": "⚖️",
        "weight": 0.30,
        "focus": "法律风险、合同条款合规性、违约责任、争议解决",
        "system_prompt": """你是一位资深企业法务顾问，专注于法律风险审查。
重点关注：
1. 合同条款是否符合《民法典》等法律规定
2. 违约责任条款是否对等、可执行
3. 争议解决条款是否有利于我方
4. 知识产权归属是否明确
5. 保密条款是否充分保护我方利益
6. 不可抗力条款是否合理
7. 合同终止和解除条件是否合法
8. 毒丸条款识别（自动续约、无限连带责任、单方修改权等）
9. 引用法规是否现行有效

输出JSON格式：
{
  "risk_score": 0-100,
  "risk_level": "low/medium/high",
  "summary": "一句话总结",
  "findings": [{"title":"", "description":"", "risk_level":"low/medium/high", "category":"法律", "suggestion":""}]
}""",
    },
    "finance": {
        "name": "财务风险Agent",
        "icon": "💰",
        "weight": 0.20,
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
8. 预付款比例是否过高（超50%需警示）

输出JSON格式：
{
  "risk_score": 0-100,
  "risk_level": "low/medium/high",
  "summary": "一句话总结",
  "findings": [{"title":"", "description":"", "risk_level":"low/medium/high", "category":"财务", "suggestion":""}]
}""",
    },
    "business": {
        "name": "商务条件Agent",
        "icon": "📋",
        "weight": 0.15,
        "focus": "业务可行性、交付条件、质量标准、合作关系",
        "system_prompt": """你是一位业务部门负责人，专注于商务条件审查。
重点关注：
1. 合同标的是否满足业务需求
2. 交付时间是否可行，是否与项目计划匹配
3. 质量标准是否明确、可验证
4. 验收流程是否合理
5. 供应商/合作方能力是否匹配
6. 售后服务和质保条款
7. 对业务连续性的影响
8. 竞业限制和排他性条款影响

输出JSON格式：
{
  "risk_score": 0-100,
  "risk_level": "low/medium/high",
  "summary": "一句话总结",
  "findings": [{"title":"", "description":"", "risk_level":"low/medium/high", "category":"商务", "suggestion":""}]
}""",
    },
    "risk_rules": {
        "name": "风控规则Agent",
        "icon": "🛡️",
        "weight": 0.20,
        "focus": "行业风控规则、毒丸条款检测、四维加权评估",
        "system_prompt": None,  # 使用规则引擎，不调用LLM
    },
    "knowledge": {
        "name": "知识图谱Agent",
        "icon": "🧠",
        "weight": 0.15,
        "focus": "历史案例匹配、企业知识库校验、合规规则检查",
        "system_prompt": None,  # 使用知识库，不调用LLM
    },
}


async def run_risk_rules_agent(text: str, contract_category: str) -> dict:
    """风控规则Agent - 基于规则引擎"""
    analysis = full_risk_analysis(text, contract_category)

    findings = []
    for risk in analysis["industry_risks"]:
        findings.append({
            "title": risk["rule_name"],
            "description": risk["description"],
            "risk_level": "high" if risk["severity"] >= 0.7 else ("medium" if risk["severity"] >= 0.5 else "low"),
            "category": "风控规则",
            "suggestion": risk["suggestion"],
            "rule_id": risk["rule_id"],
        })

    for pp in analysis["poison_pills"]:
        findings.append({
            "title": f"⚠️ {pp['name']}",
            "description": f"检测到{pp['type']}型毒丸条款：{pp['matched_text']}",
            "risk_level": "high" if pp["severity"] >= 0.7 else "medium",
            "category": "毒丸条款",
            "suggestion": "建议删除或修改此条款",
            "pattern_id": pp["pattern_id"],
        })

    return {
        "agent_name": "风控规则Agent",
        "icon": "🛡️",
        "focus": AGENT_ROLES["risk_rules"]["focus"],
        "risk_score": int(analysis["risk_score"] * 100),
        "risk_level": analysis["risk_level"],
        "summary": f"发现{analysis['industry_risks_count']}条行业风险、{analysis['poison_pills_count']}种毒丸条款，识别{analysis['identified_clauses_count']}类条款",
        "findings": findings,
        "industry_risks": analysis["industry_risks"],
        "poison_pills": analysis["poison_pills"],
        "identified_clauses": analysis["identified_clauses"],
    }


async def run_knowledge_agent(db: AsyncSession, contract_data: dict, text: str) -> dict:
    """知识图谱Agent - 基于知识库"""
    from app.services.knowledge import check_compliance, get_laws_for_contract_type

    findings = []

    # 检查合规规则
    compliance = check_compliance(text)
    for item in compliance:
        findings.append({
            "title": item["rule_name"],
            "description": item["description"],
            "risk_level": "high" if item["severity"] == "high" else "medium",
            "category": "合规检查",
            "suggestion": item.get("suggestion", ""),
        })

    # 获取相关法律条文
    contract_type = contract_data.get("contract_type", "other")
    laws = get_laws_for_contract_type(contract_type)

    return {
        "agent_name": "知识图谱Agent",
        "icon": "🧠",
        "focus": AGENT_ROLES["knowledge"]["focus"],
        "risk_score": min(len(findings) * 15, 100),
        "risk_level": "high" if len(findings) > 3 else ("medium" if len(findings) > 0 else "low"),
        "summary": f"合规检查发现{len(findings)}项问题，匹配{len(laws)}条相关法律",
        "findings": findings,
        "related_laws": laws,
    }


async def run_multi_agent_review(
    db: AsyncSession,
    contract: Contract,
    agents: Optional[List[str]] = None,
    file_content: Optional[str] = None,
) -> Dict[str, dict]:
    """运行5-Agent协作审查"""
    if agents is None:
        agents = list(AGENT_ROLES.keys())

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
    }

    text = file_content or json.dumps(contract_data, ensure_ascii=False)
    results = {}

    for agent_id in agents:
        if agent_id not in AGENT_ROLES:
            continue

        agent = AGENT_ROLES[agent_id]

        if agent_id == "risk_rules":
            # 风控规则Agent - 纯规则引擎
            contract_cat = contract_data.get("contract_type", "other")
            results[agent_id] = await run_risk_rules_agent(text, contract_cat)

        elif agent_id == "knowledge":
            # 知识图谱Agent - 基于知识库
            results[agent_id] = await run_knowledge_agent(db, contract_data, text)

        else:
            # LLM Agent (legal/finance/business)
            logger.info(f"运行{agent['name']}审查: contract_id={contract.id}")
            agent_result = await review_contract_with_ai(
                contract_data, file_content,
                system_prompt_override=agent["system_prompt"],
            )
            results[agent_id] = {
                "agent_name": agent["name"],
                "icon": agent["icon"],
                "focus": agent["focus"],
                **agent_result,
            }

    return results


async def save_agent_messages(db: AsyncSession, review_case_id: int, agent_results: Dict[str, dict]):
    """保存Agent间通信记录"""
    for agent_id, result in agent_results.items():
        for finding in result.get("findings", []):
            msg = AgentMessage(
                review_case_id=review_case_id,
                from_agent=agent_id,
                to_agent=None,
                message_type="finding",
                content=json.dumps(finding, ensure_ascii=False),
            )
            db.add(msg)
    await db.commit()


async def merge_agent_results(agent_results: Dict[str, dict]) -> dict:
    """五维加权合并审查结果"""
    all_findings = []
    weighted_score = 0.0
    total_weight = 0.0

    for agent_id, result in agent_results.items():
        agent = AGENT_ROLES.get(agent_id, {})
        weight = agent.get("weight", 0.1)
        score = result.get("risk_score", 50)

        weighted_score += score * weight
        total_weight += weight

        for finding in result.get("findings", []):
            finding["agent_source"] = agent_id
            finding["agent_name"] = agent.get("name", agent_id)
            all_findings.append(finding)

    final_score = round(weighted_score / total_weight) if total_weight > 0 else 50

    # 风险等级判定
    high_count = sum(1 for f in all_findings if f.get("risk_level") == "high")
    if high_count > 0:
        risk_level = "high"
    elif sum(1 for f in all_findings if f.get("risk_level") == "medium") > 2:
        risk_level = "medium"
    else:
        risk_level = "low"

    # 按类别分组
    by_category = {}
    for f in all_findings:
        cat = f.get("category", "其他")
        by_category.setdefault(cat, []).append(f)

    # 综合摘要
    summary_parts = []
    for agent_id, result in agent_results.items():
        icon = AGENT_ROLES.get(agent_id, {}).get("icon", "")
        summary_parts.append(f"{icon} {result.get('summary', '无摘要')}")

    return {
        "risk_level": risk_level,
        "risk_score": final_score,
        "summary": " | ".join(summary_parts),
        "total_findings": len(all_findings),
        "by_category": by_category,
        "agent_results": agent_results,
        "weights": AGENT_WEIGHTS,
    }
