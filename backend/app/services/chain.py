"""
多步推理链 - AI自主调用工具完成复杂审查
"""

import json
import logging
from typing import Optional, List, Dict, Callable, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.contract import Contract

logger = logging.getLogger(__name__)


class Tool:
    """工具定义"""
    def __init__(self, name: str, description: str, func: Callable, parameters: dict):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class AgentChain:
    """多步推理链执行器"""
    
    def __init__(self, tools: List[Tool], max_steps: int = 10):
        self.tools = {t.name: t for t in tools}
        self.max_steps = max_steps
        self.history = []
    
    async def run(self, task: str, context: dict) -> dict:
        """执行推理链"""
        self.history = []
        
        tools_desc = "\n".join([
            f"- {t.name}: {t.description}" for t in self.tools.values()
        ])
        
        system_prompt = f"""你是一个合同审查AI助手，可以使用以下工具完成审查任务：

{tools_desc}

请按照以下格式输出每一步：
{{
    "thought": "我的思考过程",
    "action": "工具名称",
    "action_input": {{...}}
}}

或者当审查完成时：
{{
    "thought": "总结分析",
    "action": "finish",
    "action_input": {{"summary": "...", "findings": [...]}}
}}

注意：
1. 每次只执行一个工具
2. 根据工具返回结果决定下一步
3. 最多执行{self.max_steps}步
4. 用中文输出"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"审查任务：{task}\n\n上下文：{json.dumps(context, ensure_ascii=False)}"},
        ]
        
        for step in range(self.max_steps):
            logger.info(f"推理链步骤 {step + 1}/{self.max_steps}")
            
            # 调用LLM
            response = await self._call_llm(messages)
            self.history.append({"step": step + 1, "response": response})
            
            # 解析响应
            try:
                action = self._parse_action(response)
            except Exception as e:
                logger.error(f"解析响应失败: {e}")
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": "请按JSON格式重新输出。"})
                continue
            
            if action.get("action") == "finish":
                return {
                    "success": True,
                    "result": action.get("action_input", {}),
                    "steps": step + 1,
                    "history": self.history,
                }
            
            # 执行工具
            tool_name = action.get("action")
            tool_input = action.get("action_input", {})
            
            if tool_name not in self.tools:
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"工具 '{tool_name}' 不存在，请使用可用的工具。"})
                continue
            
            try:
                tool_result = await self.tools[tool_name].func(**tool_input)
                self.history.append({
                    "step": step + 1,
                    "tool": tool_name,
                    "input": tool_input,
                    "output": tool_result,
                })
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"工具返回结果：\n{json.dumps(tool_result, ensure_ascii=False)}\n\n请继续分析。"})
            except Exception as e:
                logger.error(f"工具执行失败: {e}")
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"工具执行出错：{str(e)}，请尝试其他方法。"})
        
        return {
            "success": False,
            "error": "达到最大步骤数限制",
            "steps": self.max_steps,
            "history": self.history,
        }
    
    async def _call_llm(self, messages: List[dict]) -> str:
        """调用LLM"""
        import httpx
        
        api_base = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.LLM_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2000,
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        
        return data["choices"][0]["message"]["content"]
    
    def _parse_action(self, response: str) -> dict:
        """解析AI响应中的动作"""
        text = response.strip()
        
        # 尝试提取JSON
        if text.startswith("```"):
            lines = text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    in_block = False
                    continue
                if in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines)
        
        return json.loads(text)


# 预定义工具
async def search_knowledge_tool(
    keyword: str,
    contract_type: str = "all",
    db: AsyncSession = None,
) -> dict:
    """搜索领域知识"""
    from app.models.memory import ContractKnowledge
    from sqlalchemy import select
    
    query = select(ContractKnowledge).where(
        (ContractKnowledge.title.contains(keyword)) |
        (ContractKnowledge.content.contains(keyword))
    )
    
    if contract_type != "all":
        query = query.where(
            (ContractKnowledge.contract_type == "all") |
            (ContractKnowledge.contract_type.contains(contract_type))
        )
    
    query = query.limit(5)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "found": len(items),
        "items": [
            {"title": item.title, "content": item.content[:500]}
            for item in items
        ],
    }


async def get_risk_patterns_tool(
    contract_type: str,
    db: AsyncSession = None,
) -> dict:
    """获取历史风险模式"""
    from app.models.memory import RiskPattern
    from sqlalchemy import select
    
    result = await db.execute(
        select(RiskPattern)
        .where(RiskPattern.contract_types.contains(contract_type))
        .where(RiskPattern.is_active == True)
        .order_by(RiskPattern.frequency.desc())
        .limit(10)
    )
    patterns = result.scalars().all()
    
    return {
        "found": len(patterns),
        "patterns": [
            {
                "name": p.pattern_name,
                "type": p.pattern_type,
                "severity": p.severity.value,
                "frequency": p.frequency,
                "recommendation": p.recommendation,
            }
            for p in patterns
        ],
    }


async def get_similar_cases_tool(
    contract_type: str,
    risk_level: Optional[str] = None,
    db: AsyncSession = None,
) -> dict:
    """获取相似案例"""
    from app.models.memory import ReviewCase
    from sqlalchemy import select
    
    query = (
        select(ReviewCase)
        .where(ReviewCase.contract_type == contract_type)
    )
    
    if risk_level:
        query = query.where(ReviewCase.risk_level == risk_level)
    
    query = query.order_by(ReviewCase.created_at.desc()).limit(5)
    result = await db.execute(query)
    cases = result.scalars().all()
    
    return {
        "found": len(cases),
        "cases": [
            {
                "title": c.contract_title,
                "risk_level": c.risk_level,
                "risk_score": c.risk_score,
                "summary": c.review_summary[:300] if c.review_summary else "",
            }
            for c in cases
        ],
    }


async def verify_party_info_tool(
    party_name: str,
) -> dict:
    """验证合同主体信息（模拟）"""
    # 实际项目中可接入工商查询API
    return {
        "party_name": party_name,
        "verified": True,
        "note": "工商信息验证功能待接入外部API",
    }
