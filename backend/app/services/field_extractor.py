"""
关键字段自动抽取引擎
自动抓取13项关键业务字段
"""

import re
import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# 13项关键字段抽取器
FIELD_EXTRACTORS = [
    {
        "field": "contract_no",
        "name": "合同编号",
        "patterns": [
            r"(?:合同编号|合同号|编号|No\.?)[:\s]*([A-Za-z0-9\-/]+)",
            r"(?:Contract\s*No\.?)[:\s]*([A-Za-z0-9\-/]+)",
        ],
    },
    {
        "field": "party_a",
        "name": "甲方",
        "patterns": [
            r"(?:甲方|买方|需方|采购方|委托方|发包方|出租方|出让方)[:\s（(]*([^）)、,\n]{2,50})[）)]?",
            r"(?:甲方|买方)[:\s]*[：:]\s*([^\n、,]{2,50})",
        ],
    },
    {
        "field": "party_b",
        "name": "乙方",
        "patterns": [
            r"(?:乙方|卖方|供方|受托方|承包方|承租方|受让方)[:\s（(]*([^）)、,\n]{2,50})[）)]?",
            r"(?:乙方|卖方)[:\s]*[：:]\s*([^\n、,]{2,50})",
        ],
    },
    {
        "field": "sign_date",
        "name": "签约日期",
        "patterns": [
            r"(?:签订日期|签约日期|签署日期|签字日期)[:\s]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
            r"(?:\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)\s*(?:签订|签署|签字)",
        ],
    },
    {
        "field": "total_amount",
        "name": "合同总金额",
        "patterns": [
            r"(?:合同总金额|合同金额|合同总价|总金额|总价款|合同价|总价格)[:\s]*[￥¥]?\s*([\d,]+\.?\d*)\s*(?:万?元)?",
            r"(?:人民币|大写)[:\s]*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿元角分整]+)",
            r"[￥¥]\s*([\d,]+\.?\d*)",
        ],
    },
    {
        "field": "advance_ratio",
        "name": "预付款比例",
        "patterns": [
            r"(?:预付款|预付|定金|首付)[比例率额]*[:\s]*(\d+\.?\d*)\s*[%％]",
            r"(?:预付|首付|定金)[:\s]*[￥¥]?\s*([\d,]+\.?\d*)\s*(?:万?元)?",
        ],
    },
    {
        "field": "payment_deadline",
        "name": "付款期限",
        "patterns": [
            r"(?:付款期限|付款期|支付期限|账期)[:\s]*(\d+)\s*(?:天|日|工作日)",
            r"(?:验收合格后|到货后|交付后)\s*(\d+)\s*(?:天|日|工作日)\s*(?:内|以内)?\s*(?:支付|付款|付清)",
        ],
    },
    {
        "field": "delivery_date",
        "name": "交货日期",
        "patterns": [
            r"(?:交货日期|交付日期|交货期|交付期|交期)[:\s]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
            r"(?:交货|交付)[日期期]*[:\s]*(\d+)\s*(?:天|日|工作日)\s*(?:内|以内)?",
        ],
    },
    {
        "field": "warranty_period",
        "name": "质保期",
        "patterns": [
            r"(?:质保期|保修期|保质期|质量保证期)[:\s]*(\d+)\s*(?:年|月|天|日)",
            r"(?:免费保修|质保)[期限]*[:\s]*(\d+)\s*(?:年|月|天|日)",
        ],
    },
    {
        "field": "acceptance_criteria",
        "name": "验收标准",
        "patterns": [
            r"(?:验收标准|验收依据|验收条件|验收方式)[:\s]*([^\n。；]{10,200})",
            r"(?:按照|依据|根据)\s*([^\n。；]{5,100}(?:标准|规范|要求))\s*(?:进行|执行)\s*(?:验收|检验)",
        ],
    },
    {
        "field": "penalty_summary",
        "name": "违约金摘要",
        "patterns": [
            r"(?:违约金|违约责任|罚款)[比率额]*[:\s]*([^\n。]{10,200})",
            r"(?:每日|按日|每天)\s*(?:支付|缴纳)\s*(?:违约金|滞纳金)\s*[：:]*\s*([^\n。]{5,100})",
        ],
    },
    {
        "field": "dispute_resolution",
        "name": "争议解决方式",
        "patterns": [
            r"(?:争议解决|纠纷解决|管辖)[:\s]*([^\n。]{10,200})",
            r"(?:向|由)\s*([^\n。]{5,100}(?:法院|仲裁|仲裁委员会))\s*(?:提起|申请|管辖)",
        ],
    },
    {
        "field": "business_tag",
        "name": "业务分类标签",
        "patterns": [],  # 由分类引擎自动填充
    },
]


def extract_key_fields(text: str, contract_type: str = None) -> Dict[str, Optional[str]]:
    """
    从合同文本中抽取13项关键字段
    
    Args:
        text: 合同文本内容
        contract_type: 合同类型（用于业务标签）
    
    Returns:
        字段字典 {field_name: value}
    """
    if not text:
        return {}

    result = {}

    for extractor in FIELD_EXTRACTORS:
        field = extractor["field"]
        if field == "business_tag":
            result[field] = contract_type or ""
            continue

        value = None
        for pattern in extractor["patterns"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # 清理
                value = re.sub(r'\s+', ' ', value)
                if len(value) > 200:
                    value = value[:200]
                break

        result[field] = value

    # 后处理：金额格式化
    if result.get("total_amount"):
        amount_str = result["total_amount"].replace(",", "").replace("，", "")
        try:
            result["total_amount"] = str(float(amount_str))
        except ValueError:
            pass

    # 后处理：日期标准化
    for date_field in ["sign_date", "delivery_date"]:
        if result.get(date_field):
            result[date_field] = _normalize_date(result[date_field])

    # 后处理：预付款比例
    if result.get("advance_ratio"):
        ratio_str = result["advance_ratio"].replace("％", "").replace("%", "")
        try:
            result["advance_ratio"] = str(float(ratio_str))
        except ValueError:
            pass

    logger.info(f"字段抽取完成: {sum(1 for v in result.values() if v)}/{len(FIELD_EXTRACTORS)}项有值")
    return result


def _normalize_date(date_str: str) -> str:
    """标准化日期格式为 YYYY-MM-DD"""
    # 2024年1月15日 -> 2024-01-15
    match = re.match(r"(\d{4})[年/](\d{1,2})[月/](\d{1,2})[日]?", date_str)
    if match:
        y, m, d = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    # 已经是标准格式
    match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if match:
        y, m, d = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    return date_str


def extract_fields_with_llm(text: str) -> Dict[str, Optional[str]]:
    """
    使用LLM进行更精准的字段抽取（当规则引擎结果不理想时调用）
    """
    import httpx
    from app.core.config import settings

    if not settings.OPENAI_API_KEY:
        return {}

    prompt = f"""请从以下合同文本中提取13项关键字段，以JSON格式返回：

1. contract_no: 合同编号
2. party_a: 甲方
3. party_b: 乙方
4. sign_date: 签约日期(YYYY-MM-DD)
5. total_amount: 合同总金额(数字)
6. advance_ratio: 预付款比例(百分比数字)
7. payment_deadline: 付款期限(天数)
8. delivery_date: 交货日期(YYYY-MM-DD)
9. warranty_period: 质保期
10. acceptance_criteria: 验收标准
11. penalty_summary: 违约金摘要
12. dispute_resolution: 争议解决方式

无法提取的字段填null。

合同文本：
{text[:3000]}"""

    try:
        api_base = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": "你是合同分析专家，精准提取合同关键字段。只输出JSON。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"},
        }

        import asyncio

        async def _call():
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{api_base}/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

        # 如果在async上下文中
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 不能在async中直接调用，返回空
            return {}
        result_text = loop.run_until_complete(_call())
        import json
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"LLM字段抽取失败: {e}")
        return {}
