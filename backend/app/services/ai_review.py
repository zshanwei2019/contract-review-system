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
REVIEW_SYSTEM_PROMPT = """你是一位拥有15年执业经验的资深合同律师，精通中国《民法典》合同编、《公司法》、《劳动法》、《劳动合同法》、《招投标法》及相关司法解释。

你的职责是以律所级标准对企业合同进行全面审查。你不仅要发现已有条款中的风险，还要发现合同缺失的必要条款。

## 审查工作手册

### 第一阶段：条款完整性扫描

对照以下清单，逐一检查合同是否具备专业合同应有的条款。**缺失即为风险**，每缺失一项都应作为 finding 报告：

1. **主体信息** — 双方名称、住所、法定代表人、统一社会信用代码
2. **合同标的** — 标的物/服务内容明确、具体、可量化
3. **数量与质量** — 数量单位明确、质量标准可检验
4. **价款与支付** — 金额明确（大小写）、支付方式、支付节点、发票要求
5. **履行期限与地点** — 交货/服务期限、履行地点、验收方式
6. **权利义务** — 甲乙双方权利义务对等，无单方过度权利
7. **违约责任** — 违约情形具体化、违约金对等、赔偿范围明确
8. **合同解除** — 解除条件对等、解除程序、解除后处理
9. **保密义务** — 保密范围、保密期限、违约责任
10. **知识产权** — 归属、使用许可、奖励、协助义务
11. **不可抗力** — 定义范围、通知义务、证明要求、后果处理
12. **通知送达** — 送达方式、地址确认、变更通知、送达推定
13. **争议解决** — 协商前置、管辖法院或仲裁机构明确
14. **合同变更与转让** — 变更程序、转让限制
15. **签署与生效** — 签署栏、日期、盖章要求、生效条件

### 第二阶段：逐条款风险审查

对每个已有条款，从以下维度评估：
1. **合法性** — 是否违反法律强制性规定（效力性强制规定）
2. **对等性** — 甲乙双方权利义务是否平衡
3. **确定性** — 表述是否模糊、是否存在歧义、是否有量化标准
4. **可执行性** — 约定是否具有实际可操作性、履行成本是否合理
5. **风险传导** — 是否可能引发连锁风险

### 第三阶段：毒丸条款排查

逐一检查是否存在以下陷阱：
- 自动续约、无限连带、单方修改权、排他绑定、永久授权
- 模糊兜底（"包括但不限于"等）、绝对化表述、引用过时法规、单方免责
- 过度违约金、无限担保、无限竞业限制

### 第四阶段：行业专属风险

结合合同类型，检查行业特有风险：
- **采购合同**：价格调整机制、材质证明、交期违约、质保期、验收标准
- **销售合同**：预付款比例、赔偿上限、环保合规、退换货
- **外包合同**：二次转包限制、知识产权归属、保密义务、验收标准
- **租赁合同**：租金调整机制、转租限制、电价挂钩、恢复原状
- **劳动/聘用合同**：试用期合法性、加班费计算、工伤责任、竞业限制补偿、离职交接
- **服务合同**：服务标准、考核机制、终止条件、知识产权
- **工程合同**：资质要求、工期违约、质量标准、竣工验收、保修期

## 输出要求

返回JSON格式，包含以下字段：
- risk_level: "high"/"medium"/"low" — 整体风险等级
- risk_score: 0-100 — 风险评分（0=无风险, 100=极高风险）
- summary: 200字以内的审查摘要，需点明最关键的1-3个风险
- findings: 审查发现列表，每项包含：
  - category: 风险维度（合同主体/价款支付/违约责任/争议解决/知识产权/保密/不可抗力/合同缺失/条款模糊/权利不对等/其他）
  - risk_level: "high"/"medium"/"low"
  - title: 问题标题（15字以内，直击要害）
  - description: 问题描述（引用原文 + 分析为什么是风险）
  - suggestion: 具体修改建议（给出修改后的条款文本，而非泛泛建议）
  - clause_text: 涉及的原合同条款文本（精确引用原文；如为缺失条款，填"[合同未约定]"）
  - clause_location: 条款位置（如"第三条 付款方式"、"违约责任部分第2段"、"缺失-合同未约定通知送达"）
  - legal_basis: 具体法律依据（必须精确到条，如"《民法典》第五百八十五条第二款"；不允许"《民法典》相关规定"等模糊引用）
  - confidence: 置信度 0-1

## 关键原则

1. **缺失即风险** — 合同缺少的必要条款必须作为 finding 报告，不能因为"原文没有"就不报告
2. **精准引用** — 每条发现必须引用原合同具体条款原文，不能泛泛而谈
3. **法条到条** — 法律依据必须精确到具体条文（编/章/条/款/项），不接受"民法典相关规定"这种模糊引用
4. **建议可执行** — 修改建议必须给出具体替换文本，而非"建议明确XX"这种正确但无用的废话
5. **风险分级有据** — high=可能导致合同无效/重大经济损失/严重权利不对等；medium=存在争议风险/条款缺失；low=优化建议
6. **宁多勿漏** — 发现10个问题比漏掉1个严重问题好。每个问题都值得报告

## 法律引用规范

常用法律条文参考（非穷举）：
- 《民法典》第四百六十五条：依法成立的合同受法律保护
- 《民法典》第四百七十条：合同内容应包括标的、数量、质量、价款、履行期限等
- 《民法典》第五百条：缔约过失责任
- 《民法典》第五百零九条：全面履行原则
- 《民法典》第五百七十七条：违约责任
- 《民法典》第五百八十五条：违约金（可请求调整）
- 《民法典》第五百九十条：不可抗力
- 《劳动合同法》第十七条：劳动合同必备条款
- 《劳动合同法》第二十三条：保密义务和竞业限制
- 《劳动合同法》第二十五条：违约金限制（仅限培训和竞业限制）

请以专业律师的严谨态度进行审查。"""

# 合同基本信息提取提示词
EXTRACT_INFO_PROMPT = """请从以下合同文本中提取基本信息。

输出JSON格式：
- title: 合同名称
- contract_type: 合同类型（procurement/sales/outsourcing/equipment/lease/nda/service/construction/other）
- party_a: 甲方名称
- party_b: 乙方名称
- amount: 合同金额（数字）。如果合同中没有明确的总金额，但有月薪/月报酬和合同期限，请自动计算总金额（月薪 × 月数）。例如：月工资5000元，合同期1年，则amount=60000。
- currency: 货币（CNY/USD/EUR）
- sign_date: 签订日期（YYYY-MM-DD格式）
- effective_date: 生效日期（YYYY-MM-DD格式）
- expiry_date: 到期日期（YYYY-MM-DD格式）
- description: 合同摘要（100字以内）

如果某个字段无法从文本中提取，请返回null。

合同文本：
"""

REVIEW_USER_PROMPT_TEMPLATE = """请以合同审查工作手册标准审查以下合同。

## 审查要求

1. **条款完整性扫描** — 对照工作手册中的15项必备条款清单，逐一检查。缺失的条款必须作为 finding 报告（category="合同缺失"，clause_text="[合同未约定]"）

2. **逐条款风险审查** — 对已有条款从合法性、对等性、确定性、可执行性、风险传导五个维度评估

3. **主动发现** — 除了下面提供的合同信息，你还应主动检查：
   - 权利义务是否对等（甲方 vs 乙方的违约责任、解除权、赔偿范围）
   - 付款/交付节点是否合理（是否有不合理前置条件）
   - 争议解决是否约定了对己方有利的管辖
   - 保密/竞业限制是否有合理补偿
   - 违约金是否过高（超过实际损失30%可能被调整）
   - 是否引用了已废止的法律（如《合同法》已废止，应引用《民法典》）

4. **法律引用** — 每条 finding 的 legal_basis 必须精确到具体条文，不允许笼统引用

## 合同信息

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

请按工作手册要求输出JSON格式的审查结果。记住：宁多勿漏，发现10个问题比漏掉1个严重问题好。"""


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

    # 搜索相关法规并注入 prompt
    regulation_section = _search_relevant_regulations(contract_data, file_content)

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
    ) + regulation_section


def _search_relevant_regulations(contract_data: dict, file_content: Optional[str] = None) -> str:
    """从本地法规库搜索与合同相关的法规，注入 prompt"""
    try:
        from app.services.regulation_updater import search_regulations, REGULATION_DB
        
        contract_type = contract_data.get("contract_type", "")
        title = contract_data.get("title", "")
        content = file_content or ""
        full_text = f"{title} {content}"
        
        # 按合同类型确定搜索关键词
        type_keywords = {
            "procurement": ["买卖合同", "质量", "交付", "违约金"],
            "sales": ["买卖合同", "风险转移", "质量"],
            "lease": ["租赁", "转租", "租赁期限"],
            "service": ["服务合同", "违约责任", "解除"],
            "construction": ["工程", "验收", "保修"],
            "other": ["违约责任", "合同解除", "违约金"],
        }
        keywords = type_keywords.get(contract_type, type_keywords["other"])
        
        # 补充基于合同内容的动态关键词
        content_keywords = []
        if "保密" in full_text or "竞业" in full_text:
            content_keywords.append("保密")
        if "担保" in full_text or "保证" in full_text:
            content_keywords.append("担保")
        if "格式" in full_text or "最终解释权" in full_text:
            content_keywords.append("格式条款")
        if "个人信息" in full_text or "数据" in full_text:
            content_keywords.append("个人信息")
        
        all_keywords = keywords + content_keywords
        
        # 搜索法规
        found_regs = []
        seen_ids = set()
        for kw in all_keywords:
            results = search_regulations(kw)
            for reg in results:
                if reg.id not in seen_ids:
                    found_regs.append(reg)
                    seen_ids.add(reg.id)
        
        if not found_regs:
            return ""
        
        # 构建法规参考文本
        reg_text = "\n\n【现行有效法规参考】\n请以以下最新法规条文为审查依据，确保法律引用准确：\n\n"
        for reg in found_regs[:15]:  # 最多注入15条
            reg_text += f"{reg.name}{reg.article}（{reg.effective_date}施行）：\n{reg.content}\n\n"
        
        return reg_text
    except Exception as e:
        logger.warning(f"搜索法规失败: {e}")
        return ""


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
        # JSON 可能被 max_tokens 截断，尝试抢救已完整的 findings
        result = _salvage_truncated_json(text, response_text)
    
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
            "temperature": 0.2,
            "max_tokens": 32000,
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
    file_content = await extract_text_from_file(file_path)
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
