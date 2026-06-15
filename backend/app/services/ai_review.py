"""
AI智能合同审查服务
使用LLM对合同内容进行风险分析和审查建议
"""

import json
import logging
from typing import Optional
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)

# 审查提示词模板
REVIEW_SYSTEM_PROMPT = """你是一位资深的企业法务顾问，精通中国《民法典》《合同法》《劳动法》《公司法》等法律法规。
你的任务是对企业合同进行全面审查，识别潜在风险并提供专业建议。

请从以下维度进行审查：
1. **合同主体** - 甲乙方资质、签约权限、关联关系
2. **合同标的** - 标的物描述是否清晰、数量质量约定
3. **价款与支付** - 金额合理性、支付条件、发票条款
4. **履行期限** - 时间节点是否明确、延期条款
5. **违约责任** - 违约条款是否对等、赔偿范围
6. **争议解决** - 管辖约定、仲裁/诉讼选择
7. **知识产权** - 归属约定、侵权责任
8. **保密条款** - 保密范围、期限、违约后果
9. **不可抗力** - 定义是否合理、通知义务
10. **其他风险** - 合同终止、转让限制、通知送达

输出要求：
- 使用JSON格式返回
- risk_level: "high"/"medium"/"low" 整体风险等级
- risk_score: 0-100 风险评分
- summary: 200字以内的审查摘要
- findings: 审查发现列表，每项包含:
  - category: 所属维度
  - risk_level: "high"/"medium"/"low"
  - title: 问题标题
  - description: 问题描述
  - suggestion: 修改建议
  - clause_reference: 相关条款引用（如有）
  - legal_basis: 法律依据"""

# 合同基本信息提取提示词
EXTRACT_INFO_PROMPT = """请从以下合同文本中提取基本信息。

输出JSON格式：
- title: 合同名称
- contract_type: 合同类型（procurement/sales/outsourcing/equipment/lease/nda/service/construction/other）
- party_a: 甲方名称
- party_b: 乙方名称
- amount: 合同金额（数字）
- currency: 货币（CNY/USD/EUR）
- sign_date: 签订日期（YYYY-MM-DD格式）
- effective_date: 生效日期（YYYY-MM-DD格式）
- expiry_date: 到期日期（YYYY-MM-DD格式）
- description: 合同摘要（100字以内）

如果某个字段无法从文本中提取，请返回null。

合同文本：
"""

REVIEW_USER_PROMPT_TEMPLATE = """请审查以下合同：

【合同名称】{title}
【合同类型】{contract_type}
【甲方】{party_a}
【乙方】{party_b}
【合同金额】{amount} {currency}
【签订日期】{sign_date}
【生效日期】{effective_date}
【到期日期】{expiry_date}
【合同描述】{description}
【主要条款】{key_terms}
【特殊条款】{special_terms}

{file_content_section}

请按要求输出JSON格式的审查结果。"""


def _get_contract_type_label(contract_type: str) -> str:
    """获取合同类型中文标签"""
    labels = {
        "procurement": "采购合同",
        "sales": "销售合同",
        "outsourcing": "外包合同",
        "equipment": "设备合同",
        "lease": "租赁合同",
        "power_supply": "转供电合同",
        "nda": "保密协议",
        "service": "服务合同",
        "construction": "工程合同",
        "other": "其他",
    }
    return labels.get(contract_type, contract_type)


def _build_review_prompt(contract_data: dict, file_content: Optional[str] = None) -> str:
    """构建审查提示词"""
    file_content_section = ""
    if file_content:
        file_content_section = f"""【合同正文内容】
{file_content}
（以上为合同文件提取的正文内容，请重点审查）"""

    return REVIEW_USER_PROMPT_TEMPLATE.format(
        title=contract_data.get("title", "未填写"),
        contract_type=_get_contract_type_label(contract_data.get("contract_type", "")),
        party_a=contract_data.get("party_a") or "未填写",
        party_b=contract_data.get("party_b") or "未填写",
        amount=contract_data.get("amount") or "未填写",
        currency=contract_data.get("currency") or "CNY",
        sign_date=contract_data.get("sign_date") or "未填写",
        effective_date=contract_data.get("effective_date") or "未填写",
        expiry_date=contract_data.get("expiry_date") or "未填写",
        description=contract_data.get("description") or "无",
        key_terms=contract_data.get("key_terms") or "无",
        special_terms=contract_data.get("special_terms") or "无",
        file_content_section=file_content_section,
    )


def _parse_ai_response(response_text: str) -> dict:
    """解析AI返回的JSON结果"""
    # 尝试提取JSON内容
    text = response_text.strip()
    
    # 处理markdown代码块包裹的JSON
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
    
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # 如果解析失败，构造一个基本结果
        result = {
            "risk_level": "medium",
            "risk_score": 50,
            "summary": response_text[:500] if len(response_text) > 500 else response_text,
            "findings": [],
        }
    
    # 确保必要字段存在
    result.setdefault("risk_level", "medium")
    result.setdefault("risk_score", 50)
    result.setdefault("summary", "")
    result.setdefault("findings", [])
    
    return result


async def review_contract_with_ai(
    contract_data: dict,
    file_content: Optional[str] = None,
    system_prompt_override: Optional[str] = None,
) -> dict:
    """
    使用AI对合同进行智能审查
    
    Args:
        contract_data: 合同基本信息字典
        file_content: 合同文件提取的文本内容（可选）
    
    Returns:
        审查结果字典，包含 risk_level, risk_score, summary, findings
    """
    # 检查是否配置了API Key
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY未配置，使用模拟审查结果")
        return _mock_review(contract_data)
    
    try:
        import httpx
        
        prompt = _build_review_prompt(contract_data, file_content)
        
        system_prompt = system_prompt_override or REVIEW_SYSTEM_PROMPT
        
        api_base = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 4000,
            "response_format": {"type": "json_object"},
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        
        ai_text = data["choices"][0]["message"]["content"]
        result = _parse_ai_response(ai_text)
        
        logger.info(f"AI审查完成: risk_level={result['risk_level']}, risk_score={result['risk_score']}")
        return result
        
    except Exception as e:
        logger.error(f"AI审查失败: {e}", exc_info=True)
        # 降级到模拟审查
        return _mock_review(contract_data)


async def extract_file_content(file_path: str) -> Optional[str]:
    """从合同文件中提取文本内容"""
    import os
    
    if not os.path.exists(file_path):
        return None
    
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()[:10000]  # 限制长度
        
        elif ext == ".pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                    if len(text) > 10000:
                        break
                doc.close()
                return text[:10000]
            except ImportError:
                logger.warning("PyMuPDF未安装，无法解析PDF")
                return None
        
        elif ext in (".doc", ".docx"):
            try:
                import docx
                doc = docx.Document(file_path)
                text = "\n".join([p.text for p in doc.paragraphs])
                return text[:10000]
            except ImportError:
                logger.warning("python-docx未安装，无法解析Word文档")
                return None
        
        return None
    except Exception as e:
        logger.error(f"文件内容提取失败: {e}")
        return None


def _mock_review(contract_data: dict) -> dict:
    """模拟审查结果（当AI不可用时）"""
    findings = []
    risk_score = 0
    
    # 基于规则的简单风险检测
    amount = contract_data.get("amount")
    if amount and float(amount) > 1000000:
        findings.append({
            "category": "价款与支付",
            "risk_level": "high",
            "title": "大额合同风险",
            "description": f"合同金额为{amount}元，属于大额合同，需重点关注支付条件和资金安全。",
            "suggestion": "建议分期支付，设置付款里程碑，并要求提供履约保证金或银行保函。",
            "clause_reference": "",
            "legal_basis": "《民法典》第六百零七条",
        })
        risk_score += 25
    
    if not contract_data.get("party_a") or not contract_data.get("party_b"):
        findings.append({
            "category": "合同主体",
            "risk_level": "medium",
            "title": "合同主体信息不完整",
            "description": "甲方或乙方信息缺失，可能导致合同效力问题。",
            "suggestion": "补充完整的甲乙方名称、统一社会信用代码、法定代表人等信息。",
            "clause_reference": "",
            "legal_basis": "《民法典》第四百七十条",
        })
        risk_score += 15
    
    if not contract_data.get("effective_date") or not contract_data.get("expiry_date"):
        findings.append({
            "category": "履行期限",
            "risk_level": "medium",
            "title": "合同期限不明确",
            "description": "合同生效日期或到期日期缺失，可能导致履行争议。",
            "suggestion": "明确约定合同生效条件、有效期限和续约条款。",
            "clause_reference": "",
            "legal_basis": "《民法典》第五百零二条",
        })
        risk_score += 15
    
    if not contract_data.get("description") and not contract_data.get("key_terms"):
        findings.append({
            "category": "合同标的",
            "risk_level": "medium",
            "title": "合同内容描述不足",
            "description": "缺少合同描述和主要条款信息，难以评估合同风险。",
            "suggestion": "建议上传合同文件或补充合同主要内容描述。",
            "clause_reference": "",
            "legal_basis": "《民法典》第四百七十条",
        })
        risk_score += 10
    
    # 检查违约责任
    description = contract_data.get("description", "") + " " + (contract_data.get("key_terms", "") or "")
    if "违约" not in description and "责任" not in description:
        findings.append({
            "category": "违约责任",
            "risk_level": "high",
            "title": "违约责任条款缺失",
            "description": "合同未明确违约责任，可能导致违约后无法有效追责。",
            "suggestion": "建议明确违约责任条款，包括违约金计算方式、赔偿范围和上限。",
            "clause_reference": "违约责任条款",
            "legal_basis": "《民法典》第五百七十七条、第五百八十五条",
        })
        risk_score += 20
    
    # 检查争议解决
    if "仲裁" not in description and "法院" not in description and "诉讼" not in description:
        findings.append({
            "category": "争议解决",
            "risk_level": "medium",
            "title": "争议解决条款缺失",
            "description": "合同未明确争议解决方式，可能导致争议发生时无法有效解决。",
            "suggestion": "建议明确争议解决方式和管辖法院/仲裁机构。",
            "clause_reference": "争议解决条款",
            "legal_basis": "《民事诉讼法》第三十四条",
        })
        risk_score += 15
    
    # 如果没有发现问题
    if not findings:
        findings.append({
            "category": "综合评估",
            "risk_level": "low",
            "title": "基础信息审查通过",
            "description": "合同基本信息填写完整，未发现明显风险。建议上传合同文件进行深度AI审查。",
            "suggestion": "上传合同原文文件，启用AI深度审查以获取更全面的风险分析。",
            "clause_reference": "",
            "legal_basis": "",
        })
        risk_score = 10
    
    # 确定整体风险等级
    high_count = sum(1 for f in findings if f["risk_level"] == "high")
    medium_count = sum(1 for f in findings if f["risk_level"] == "medium")
    
    if high_count > 0:
        risk_level = "high"
    elif medium_count > 0:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    risk_score = min(risk_score, 100)
    
    summary_parts = []
    if high_count:
        summary_parts.append(f"发现{high_count}项高风险")
    if medium_count:
        summary_parts.append(f"{medium_count}项中风险")
    if not summary_parts:
        summary_parts.append("未发现明显风险")
    
    summary = f"审查完成，{', '.join(summary_parts)}。" + (
        "建议上传合同原文进行AI深度审查以获取更全面的分析。"
        if not contract_data.get("file_path") else
        "请查看详细审查意见。"
    )
    
    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "summary": summary,
        "findings": findings,
    }


async def extract_contract_info(file_path: str) -> dict:
    """
    从合同文件中提取基本信息
    """
    from app.services.file_parser import extract_text_from_file
    
    # 提取文件内容
    file_content = extract_text_from_file(file_path)
    if not file_content or len(file_content.strip()) < 50:
        return None
    
    # 截取前3000字符用于提取（避免token浪费）
    file_content_for_extract = file_content[:3000] + ("...\n[内容已截断]" if len(file_content) > 3000 else "")
    
    # 调用AI提取
    if not settings.OPENAI_API_KEY:
        return None
    
    try:
        import httpx
        
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        
        prompt = EXTRACT_INFO_PROMPT + file_content_for_extract
        
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }
        
        response = httpx.post(
            f"{settings.OPENAI_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # 清理markdown代码块标记
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        return json.loads(content)
        
    except Exception as e:
        logger.error(f"提取合同信息失败: {str(e)}")
        return None
