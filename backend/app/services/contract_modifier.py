"""
合同自动修改服务
根据AI审查发现生成修改建议并支持一键应用
"""
import json
import os
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.contract import Contract, ContractVersion
from app.models.review import ReviewTask, ReviewOpinion
from app.core.config import settings

# RAG 注入 (条款级 RAG 检索)
from app.services.contract_rag import ContractRAG, _format_rag_blocks
import logging as _logging
_rag_logger = _logging.getLogger("contract_rag")


class ModificationType(str, Enum):
    """修改类型"""
    REPLACE = "replace"  # 替换内容
    INSERT = "insert"    # 插入内容
    DELETE = "delete"    # 删除内容
    REWRITE = "rewrite"  # 重写段落


class ModificationPriority(str, Enum):
    """修改优先级"""
    CRITICAL = "critical"  # 必须修改
    HIGH = "high"        # 强烈建议
    MEDIUM = "medium"    # 建议修改
    LOW = "low"          # 可选修改


@dataclass
class ModificationSuggestion:
    """修改建议"""
    id: str
    finding_id: str  # 关联的审查发现ID
    clause: str  # 涉及的条款
    original_text: str  # 原始文本
    suggested_text: str  # 建议修改后的文本
    modification_type: ModificationType
    priority: ModificationPriority
    reason: str  # 修改理由
    legal_basis: str  # 法律依据
    risk_if_not_modified: str  # 不修改的风险
    position: Optional[Dict[str, Any]] = None  # 在文档中的位置
    applied: bool = False


@dataclass
class ModificationResult:
    """修改结果"""
    contract_id: int
    suggestions: List[ModificationSuggestion]
    applied_count: int
    total_suggestions: int
    modified_content: Optional[str] = None
    version_id: Optional[int] = None
    original_content: Optional[str] = None
    diff_summary: Optional[str] = None


def _cn_clause_num(n):
    """数字转中文条款号"""
    cn = {1:"一",2:"二",3:"三",4:"四",5:"五",6:"六",7:"七",8:"八",9:"九",10:"十",
          11:"十一",12:"十二",13:"十三",14:"十四",15:"十五",16:"十六",17:"十七",18:"十八",19:"十九",20:"二十"}
    if n <= 20:
        return cn.get(n, str(n))
    if n < 100:
        a, b = divmod(n, 10)
        return cn.get(a, str(a)) + "十" + (cn.get(b, str(b)) if b else "")
    return str(n)



class ContractModifier:
    """合同修改器"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
        self.model = settings.LLM_MODEL or "gpt-4-turbo-preview"
    
    async def generate_modification_suggestions(
        self,
        db: AsyncSession,
        contract_id: int,
        review_task_id: Optional[int] = None
    ) -> List[ModificationSuggestion]:
        """根据审查发现生成修改建议"""
        
        # 获取合同信息
        contract = await db.get(Contract, contract_id)
        if not contract:
            raise ValueError(f"合同 {contract_id} 不存在")
        
        # 获取审查任务
        if review_task_id:
            review_task = await db.get(ReviewTask, review_task_id)
        else:
            result = await db.execute(
                select(ReviewTask)
                .where(ReviewTask.contract_id == contract_id)
                .order_by(ReviewTask.created_at.desc())
                .limit(1)
            )
            review_task = result.scalar_one_or_none()
        
        if not review_task:
            raise ValueError(f"合同 {contract_id} 没有审查记录")
        
        # 获取审查发现
        result = await db.execute(
            select(ReviewOpinion)
            .where(ReviewOpinion.review_task_id == review_task.id)
        )
        findings = result.scalars().all()
        
        if not findings:
            return []
        
        # 构建审查发现列表
        findings_list = []
        for finding in findings:
            findings_list.append({
                "id": finding.id,
                "clause": finding.clause_reference or "",
                "content": finding.content,
                "risk_level": finding.risk_level or "medium",
                "category": finding.opinion_type or "",
                "suggestion": finding.suggestion or ""
            })
        
        # 使用AI生成修改建议
        if self.api_key:
            suggestions = await self._generate_with_ai(contract, findings_list)
        else:
            suggestions = self._generate_with_rules(contract, findings_list)
        
        return suggestions
    
    async def _generate_with_ai(
        self,
        contract: Contract,
        findings: List[Dict]
    ) -> List[ModificationSuggestion]:
        """使用AI生成修改建议"""
        import httpx
        
        # RAG 检索 (对每个 finding 检索 top-2 类似条款)
        rag_blocks = []
        try:
            rag = ContractRAG()
            for f in findings:
                clause_text = f.get("content", "") or f.get("clause", "") or ""
                if clause_text:
                    ctx = rag.retrieve(clause_text, top_k=2)
                    if not ctx.is_empty():
                        rag_blocks.append(ctx)
            _rag_logger.info(f"RAG 注入: {len(rag_blocks)} 个检索块")
        except Exception as e:
            _rag_logger.warning(f"RAG 检索失败, 继续: {e}")
        
        prompt = self._build_modification_prompt(contract, findings, rag_blocks)
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:  # 120秒超时 (生成修改建议)
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": """你是一位拥有15年执业经验的资深合同律师，擅长条款级风险分析和修改建议起草。

## 你的工作方式

1. **逐条分析** — 对每个审查发现，定位到具体条款，分析风险根源
2. **给出修改文本** — 不要说"建议明确XX"，而是直接给出修改后的条款全文
3. **引用法条** — 每条建议必须附上具体法律依据（精确到条/款）
4. **风险量化** — 明确不修改会导致什么后果（经济损失/合同无效/争议风险）
5. **优先级排序** — critical=必须改否则合同有重大风险；high=强烈建议改；medium=建议改；low=可选优化

## 参考信息使用规则

- RAG检索到的历史案例仅作参考，不能直接复制
- 反例（example_bad）展示常见错误模式，用于识别类似问题
- 正例（example_good）展示推荐写法，作为修改建议的参考方向

返回JSON格式的修改建议数组。"""
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.3,
                        "max_tokens": 8000
                    }
                )
                
                if response.status_code != 200:
                    return self._generate_with_rules(contract, findings)
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            try:
                # 提取JSON部分
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    try:
                        suggestions_data = json.loads(json_str)
                    except json.JSONDecodeError:
                        # JSON 可能被截断，尝试补全
                        # 找最后一个完整的对象
                        last_brace = json_str.rfind('}')
                        if last_brace > 0:
                            json_str = json_str[:last_brace+1] + ']'
                            suggestions_data = json.loads(json_str)
                        else:
                            raise
                else:
                    # 尝试清理内容后再解析
                    clean_content = content.strip()
                    if clean_content.startswith('```json'):
                        clean_content = clean_content[7:]
                    if clean_content.endswith('```'):
                        clean_content = clean_content[:-3]
                    suggestions_data = json.loads(clean_content.strip())
                
                suggestions = []
                for i, data in enumerate(suggestions_data):
                    suggestion = ModificationSuggestion(
                        id=f"MOD-{contract.id}-{i+1}",
                        finding_id=data.get("finding_id", f"UNKNOWN-{i+1}"),
                        clause=data.get("clause", "未知条款"),
                        original_text=data.get("original_text", ""),
                        suggested_text=data.get("suggested_text", ""),
                        modification_type=data.get("modification_type", "replace"),
                        priority=data.get("priority", "medium"),
                        reason=data.get("reason", ""),
                        legal_basis=data.get("legal_basis", ""),
                        risk_if_not_modified=data.get("risk_if_not_modified", "")
                    )
                    suggestions.append(suggestion)
                
                return suggestions
                
            except json.JSONDecodeError:
                return self._generate_with_rules(contract, findings)
        except httpx.ReadTimeout:
            print("AI API调用超时 (120s)，使用规则引擎生成修改建议")
            return self._generate_with_rules(contract, findings)
        except Exception as e:
            print(f"AI API调用失败: {str(e)}")
            return self._generate_with_rules(contract, findings)
    
    def _build_modification_prompt(self, contract: Contract, findings: List[Dict], rag_blocks: list = None) -> str:
        """构建修改建议提示词 (含 RAG 检索块 + 反例库)"""
        rag_section = _format_rag_blocks(rag_blocks or [])
        examples_block = _build_examples_block(findings)

        return f"""请根据以下审查发现，为合同生成具体的修改建议。

## 合同信息
- 合同名称：{contract.title}
- 合同类型：{contract.contract_type.value if contract.contract_type else '未指定'}
- 甲方：{contract.party_a or '未指定'}
- 乙方：{contract.party_b or '未指定'}
- 金额：{contract.amount or '未指定'} {contract.currency or 'CNY'}

## 审查发现的问题
{json.dumps(findings, ensure_ascii=False, indent=2)}
{rag_section}
{examples_block}
## 输出要求

请为每个问题生成具体的修改建议。注意：
1. **suggested_text 必须是完整的修改后条款文本**，不是"建议增加..."这种描述
2. **legal_basis 必须精确到条**，如"《民法典》第五百八十五条第二款"
3. **reason 要说明风险根源**，不只是"建议修改以降低风险"
4. **risk_if_not_modified 要描述具体后果**，如"可能导致甲方承担超出实际损失30%的违约金"

返回JSON格式：
[
  {{
    "finding_id": "审查发现ID",
    "clause": "涉及的条款名称",
    "original_text": "原始条款全文",
    "suggested_text": "修改后的完整条款文本",
    "modification_type": "replace/insert/delete/rewrite",
    "priority": "critical/high/medium/low",
    "reason": "风险根源分析",
    "legal_basis": "具体法条引用",
    "risk_if_not_modified": "不修改的具体后果"
  }}
]

## 反例参考说明
- example_bad 展示了同类条款的常见错误写法
- example_good 展示了推荐的安全写法
- 请参照 example_good 的方向给出 suggested_text
"""
    
    def _generate_with_rules(
        self,
        contract: Contract,
        findings: List[Dict]
    ) -> List[ModificationSuggestion]:
        """基于规则生成修改建议"""
        suggestions = []
        
        # 根据风险等级生成不同的修改建议
        for i, finding in enumerate(findings):
            risk_level = finding.get("risk_level", "medium")
            category = finding.get("category", "")
            content = finding.get("content", "")
            clause = finding.get("clause", "")
            suggestion = finding.get("suggestion", "")
            
            # 根据问题类型生成修改建议
            modification_type = ModificationType.REPLACE
            # 优先使用审查意见中的 suggestion（它是具体修改建议）
            # 但如果 suggestion 是描述性语言（如"将该款修改为：..."），则提取冒号后的内容
            if suggestion and len(suggestion) > 20:
                # 尝试提取 "修改为：XXX" 中的实际条款文本
                import re as _re
                m = _re.search(r'修改为[：:\s]*[\'\'""]?(.+?)[\'\'""]?$', suggestion, _re.DOTALL)
                if m:
                    suggested_text = m.group(1).strip()
                else:
                    suggested_text = suggestion
            else:
                suggested_text = self._generate_default_suggestion(category, content)
            
            # 确定优先级
            if risk_level == "critical":
                priority = ModificationPriority.CRITICAL
            elif risk_level == "high":
                priority = ModificationPriority.HIGH
            elif risk_level == "medium":
                priority = ModificationPriority.MEDIUM
            else:
                priority = ModificationPriority.LOW
            
            # 生成修改建议
            mod_suggestion = ModificationSuggestion(
                id=f"MOD-{contract.id}-{i+1}",
                finding_id=str(finding.get("id", f"UNKNOWN-{i+1}")),
                clause=clause,
                original_text=content[:200] if content else "",
                suggested_text=suggested_text,
                modification_type=modification_type,
                priority=priority,
                reason=self._generate_reason(category, content),
                legal_basis=self._generate_legal_basis(category),
                risk_if_not_modified=self._generate_risk_description(risk_level, category)
            )
            suggestions.append(mod_suggestion)
        
        return suggestions
    
    def _generate_default_suggestion(self, category: str, content: str) -> str:
        """生成默认修改建议 - 返回实际条款文本"""
        suggestions_map = {
            "违约责任": "任何一方违反本合同约定的，应承担违约责任。违约方应向守约方支付违约金，违约金按合同总金额的万分之五/日计算；违约金不足以弥补守约方损失的，违约方还应赔偿守约方的实际损失。赔偿范围包括但不限于直接损失、预期利益损失、律师费、诉讼费等合理费用。",
            "违约": "任何一方违反本合同约定的，应承担违约责任。违约方应向守约方支付违约金，违约金按合同总金额的万分之五/日计算；违约金不足以弥补守约方损失的，违约方还应赔偿守约方的实际损失。赔偿范围包括但不限于直接损失、预期利益损失、律师费、诉讼费等合理费用。",
            "付款条件": "甲方应在收到乙方开具的合规发票后【30】个工作日内支付款项。甲方以银行转账方式将款项支付至乙方指定账户。乙方应在付款前向甲方提供等额、合法、有效的增值税专用发票。如甲方逾期付款，应按未付金额的万分之三/日向乙方支付违约金。",
            "价款支付": "甲方应按约定的支付方式和期限向乙方支付款项。甲方以银行转账方式将款项支付至乙方指定账户。乙方应在付款前向甲方提供等额、合法、有效的发票。如甲方逾期付款，应按未付金额的万分之三/日向乙方支付违约金。",
            "交付条款": "乙方应于【日期】前将符合合同约定的标的物交付至甲方指定地点。交付前标的物的毁损、灭失风险由乙方承担，交付后由甲方承担。甲方应在收到标的物后【7】个工作日内完成验收，验收不合格的，乙方应在【15】个工作日内免费更换或修复。",
            "知识产权": "本合同履行过程中产生的新知识产权（前景知识产权）归甲方所有。双方各自原有的知识产权（背景知识产权）仍归各自所有。乙方不得将甲方的技术资料、商业信息用于本合同之外的任何目的。未经甲方书面同意，乙方不得将相关知识产权转让或授权给第三方。",
            "保密条款": "双方对在本合同履行过程中获知的对方商业秘密、技术秘密及其他保密信息承担保密义务。保密期限为合同终止后【3】年。保密信息不包括：已公开的信息、合法渠道获得的信息、法律要求披露的信息。违反保密义务的一方应赔偿对方因此遭受的全部损失。",
            "保密": "双方对在本合同履行过程中获知的对方商业秘密、技术秘密及其他保密信息承担保密义务。保密期限为合同终止后【3】年。保密信息不包括：已公开的信息、合法渠道获得的信息、法律要求披露的信息。违反保密义务的一方应赔偿对方因此遭受的全部损失。",
            "争议解决": "因本合同引起的或与本合同有关的任何争议，双方应首先通过友好协商解决；协商不成的，任何一方均有权向甲方所在地有管辖权的人民法院提起诉讼。争议解决期间，合同的继续履行部分不受影响。",
            "争议": "因本合同引起的或与本合同有关的任何争议，双方应首先通过友好协商解决；协商不成的，任何一方均有权向甲方所在地有管辖权的人民法院提起诉讼。争议解决期间，合同的继续履行部分不受影响。",
            "合同期限": "本合同自双方签字盖章之日起生效，有效期至【日期】止。合同到期前【30】日，双方可协商续约。任何一方需提前终止合同的，应提前【30】日书面通知对方，并承担相应的违约责任。",
            "质量标准": "标的物应符合国家相关质量标准及合同约定的技术规格。乙方提供的产品/服务质量保证期为【12】个月，自验收合格之日起算。保证期内出现质量问题的，乙方应免费维修或更换。",
            "质量": "标的物应符合国家相关质量标准及合同约定的技术规格。乙方提供的产品/服务质量保证期为【12】个月，自验收合格之日起算。保证期内出现质量问题的，乙方应免费维修或更换。",
            "不可抗力": "因不可抗力导致一方不能履行合同义务的，应在不可抗力发生后【15】日内书面通知对方，并提供相关证明文件。不可抗力持续超过【30】日的，任何一方有权解除合同。不可抗力包括但不限于自然灾害、战争、政府行为、疫情等。",
            "合同主体": "双方确认，本合同主体信息如下：甲方为依法成立并存续的企业法人，具备签署和履行本合同的资格和能力。乙方为具备完全民事行为能力的自然人/依法成立并存续的法人或其他组织。双方保证其代表已获得充分授权签署本合同。",
        }
        for key, suggestion in suggestions_map.items():
            if key in category:
                return suggestion
        # 根据内容关键词推断
        if "歧视" in content or "遗传" in content:
            return "乙方保证其身体健康状况能够胜任本协议约定的岗位工作，如因自身健康原因无法继续履行协议，应按照本协议规定提前通知甲方。甲方不得以与履行岗位无关的健康信息作为歧视依据。"
        if "竞业" in content or "兼职" in content:
            return "乙方受聘期间不得自营或为他人经营与甲方同类或类似的业务。若乙方违反此项义务，所得收益归甲方所有，并应赔偿甲方因此遭受的实际损失。"
        if "单方" in content and ("调整" in content or "修改" in content):
            return "任何对本合同条款的修改或补充，须经双方书面协商一致，并签订书面补充协议。补充协议与本合同具有同等法律效力。"
        if "试用期" in content:
            return "本协议不设试用期。乙方自协议生效之日起即按约定岗位履行职责。"
        if "规章" in content and "制度" in content:
            return "乙方应遵守甲方已向乙方公示或书面告知的规章制度，规章制度的变更或新增须经乙方签收确认后对其发生效力。甲方规章制度如与本协议抵触，以本协议为准。"
        if "解除" in content or "终止" in content:
            return "乙方严重违反甲方规章制度，给甲方造成重大损害的（重大损害标准以附件形式明确），甲方可以解除本协议。甲方应在解除前书面通知乙方并说明理由。"
        if "法律" in content and ("废止" in content or "民法通则" in content or "合同法" in content):
            return "根据《中华人民共和国民法典》及相关法律规定，甲乙双方经平等协商一致，自愿签订本协议，共同遵守本协议所列条款。"
        return "建议修改此条款以降低合同风险，明确双方权利义务，保护委托方合法权益。"

    def _generate_reason(self, category: str, content: str) -> str:
        """生成修改理由"""
        if "违约" in category:
            return "明确违约责任有助于在对方违约时快速获得赔偿，减少争议。"
        elif "付款" in category:
            return "明确付款条件可以避免付款争议，确保资金安全。"
        elif "交付" in category:
            return "明确交付条款可以确保按时收到符合要求的标的物。"
        elif "知识产权" in category:
            return "明确知识产权归属可以避免后续的知识产权纠纷。"
        elif "保密" in category:
            return "明确保密义务可以保护商业秘密和敏感信息。"
        elif "争议" in category:
            return "明确争议解决方式可以降低争议解决成本和时间。"
        else:
            return "修改此条款可以降低合同风险，保护委托方合法权益。"
    
    def _generate_legal_basis(self, category: str) -> str:
        """生成法律依据"""
        basis_map = {
            "违约": "《中华人民共和国民法典》第五百七十七条、第五百八十五条",
            "付款": "《中华人民共和国民法典》第六百二十六条、第六百二十七条",
            "交付": "《中华人民共和国民法典》第六百零一条、第六百零二条",
            "知识产权": "《中华人民共和国民法典》第八百四十三条、第八百四十四条",
            "保密": "《中华人民共和国民法典》第五百零一条",
            "争议": "《中华人民共和国民事诉讼法》第三十四条",
            "质量": "《中华人民共和国民法典》第六百一十五条、第六百一十六条",
        }
        
        for key, basis in basis_map.items():
            if key in category:
                return basis
        
        return "《中华人民共和国民法典》合同编相关规定"
    
    def _generate_risk_description(self, risk_level: str, category: str) -> str:
        """生成风险描述"""
        if risk_level == "critical":
            return f"该{category}条款存在重大风险，可能导致合同无效或重大经济损失。"
        elif risk_level == "high":
            return f"该{category}条款存在较高风险，可能导致重大争议或损失。"
        elif risk_level == "medium":
            return f"该{category}条款存在一定风险，建议修改以降低潜在风险。"
        else:
            return f"该{category}条款风险较低，修改可进一步优化合同条款。"
    
    async def apply_modification(
        self,
        db: AsyncSession,
        contract_id: int,
        suggestion_ids: List[str],
        user_id: int
    ) -> ModificationResult:
        """应用修改建议"""
        
        # 获取合同
        contract = await db.get(Contract, contract_id)
        if not contract:
            raise ValueError(f"合同 {contract_id} 不存在")
        
        # 获取审查记录
        result = await db.execute(
            select(ReviewTask)
            .where(ReviewTask.contract_id == contract_id)
            .order_by(ReviewTask.created_at.desc())
            .limit(1)
        )
        review_task = result.scalar_one_or_none()
        
        if not review_task:
            raise ValueError(f"合同 {contract_id} 没有审查记录")
        
        # 直接基于审查发现生成修改建议（使用规则引擎，避免调用AI超时）
        findings_result = await db.execute(
            select(ReviewOpinion)
            .where(ReviewOpinion.review_task_id == review_task.id)
        )
        findings = findings_result.scalars().all()
        
        if not findings:
            raise ValueError(f"合同 {contract_id} 没有审查发现")
        
        # 构建审查发现列表
        findings_list = []
        for finding in findings:
            findings_list.append({
                "id": finding.id,
                "clause": finding.clause_reference or "",
                "content": finding.content,
                "risk_level": finding.risk_level or "medium",
                "category": finding.opinion_type or "",
                "suggestion": finding.suggestion or ""
            })
        
        # 使用规则引擎生成修改建议（快速，不调用AI）
        suggestions = self._generate_with_rules(contract, findings_list)
        
        # 过滤出要应用的建议
        suggestions_to_apply = [s for s in suggestions if s.id in suggestion_ids]
        
        if not suggestions_to_apply:
            raise ValueError("没有找到要应用的修改建议")
        
        # P0: 提取原始合同文本，让AI基于原文改写而非凭空生成
        orig_content = ""
        if contract.file_path:
            import os as _os
            if _os.path.exists(contract.file_path):
                try:
                    from app.services.file_parser import extract_text_from_file
                    orig_content = await extract_text_from_file(contract.file_path)
                except Exception as e:
                    print(f"提取合同原文失败: {e}")
        # 如果文件解析失败，用 description 作为兜底
        if not orig_content or len(orig_content) < 100:
            orig_content = contract.description or ""

        # 使用AI重写合同内容 (传入原文+原始审查意见，走改写模式)
        modified_content = await self.rewrite_contract_with_ai(
            contract, suggestions_to_apply, original_content=orig_content,
            review_findings=findings_list
        )
        
        # 生成修改摘要
        modification_summary = []
        for suggestion in suggestions_to_apply:
            modification_summary.append(
                f"[{suggestion.clause}] {suggestion.reason}"
            )
            suggestion.applied = True
        
        # 更新合同描述
        if contract.description:
            contract.description += "\n\n--- 修改记录 ---\n" + "\n".join(modification_summary)
        else:
            contract.description = "--- 修改记录 ---\n" + "\n".join(modification_summary)
        
        # 创建新版本（存储修改后内容）
        version = ContractVersion(
            contract_id=contract.id,
            version_no=await self._get_next_version(db, contract.id),
            change_summary=f"根据AI审查建议修改了 {len(suggestions_to_apply)} 处",
            uploaded_by=user_id
        )
        db.add(version)
        
        await db.commit()
        await db.refresh(contract)
        await db.refresh(version)
        
        # 生成差异摘要
        diff_summary = f"已应用 {len(suggestions_to_apply)} 个修改建议：\n"
        for s in suggestions_to_apply:
            diff_summary += f"- {s.clause}: {s.reason}\n"
        
        return ModificationResult(
            contract_id=contract.id,
            suggestions=suggestions,
            applied_count=len(suggestions_to_apply),
            total_suggestions=len(suggestions),
            modified_content=modified_content,
            version_id=version.id,
            original_content=contract.description,
            diff_summary=diff_summary
        )
    
    async def rewrite_contract_with_ai(
        self,
        contract: Contract,
        suggestions_to_apply: List[ModificationSuggestion],
        original_content: str = "",
        review_findings: List[Dict] = None
    ) -> str:
        """使用AI重写合同内容，应用修改建议。
        当 original_content > 100 字符时, 使用改写模式; 否则生成模式。
        当 review_findings 提供时，直接传原始审查意见给AI，绕过规则引擎中间层。
        """
        if not self.api_key:
            return self._rewrite_with_rules(contract, suggestions_to_apply)
        
        import httpx
        
        # 构建合同信息
        contract_info = f"""合同名称：{contract.title}
合同类型：{contract.contract_type.value if hasattr(contract.contract_type, 'value') else (contract.contract_type or '未指定')}
甲方：{contract.party_a or '未指定'}
乙方：{contract.party_b or '未指定'}
合同金额：{contract.amount or '未指定'} {contract.currency or 'CNY'}
签订日期：{contract.sign_date or '未指定'}
生效日期：{contract.effective_date or '未指定'}
到期日期：{contract.expiry_date or '未指定'}
合同摘要：{contract.description or '无'}"""
        
        # 构建修改建议列表 — 优先使用原始审查意见，跳过规则引擎中间层
        if review_findings:
            # 直接传原始审查意见给 AI，让 AI 自己理解问题并生成针对性修改
            findings_text = ""
            for i, f in enumerate(review_findings, 1):
                findings_text += f"""
审查问题{i}:
- 涉及条款：{f.get('clause', '未指定')}
- 原条款文本：{f.get('clause_text', '[未提取到原条款]')}
- 问题描述：{f.get('content', '')}
- 风险等级：{f.get('risk_level', 'medium')}
- 问题类型：{f.get('category', '')}
- 审查建议：{f.get('suggestion', '')}"""
            suggestions_section = f"""【审查发现的问题】
以下是合同审查中发现的实际问题，请基于这些问题直接修改合同条款：
{findings_text}"""
        else:
            # 降级：使用规则引擎生成的修改建议
            suggestions_text = ""
            for i, s in enumerate(suggestions_to_apply, 1):
                suggestions_text += f"""
修改建议{i}:
- 涉及条款：{s.clause}
- 原始内容：{s.original_text}
- 建议修改为：{s.suggested_text}
- 修改理由：{s.reason}
- 法律依据：{s.legal_basis}
- 优先级：{s.priority.value}"""
            suggestions_section = f"""【需要应用的修改建议】
{suggestions_text}"""
        
        has_original = bool(original_content) and len(original_content) > 100

        if has_original:
            truncated = original_content[:12000]
            prompt = f"""请基于以下原始合同和审查意见，输出一份全面优化后的合同。

【合同信息】
{contract_info}

【原始合同正文】
{truncated}

{suggestions_section}

【修订指引】
以上审查意见是**最低修改要求**，你必须100%解决每一个问题。在此基础上，你还应当主动发现并修复原合同中审查未覆盖的其他问题。

具体操作：
1. 逐一解决审查意见中的每个问题——在合同条款中实质性消除该风险
2. 对照系统提示中的"条款完整性"清单，补充原合同缺失的必要条款
3. 将所有模糊表述细化为具体约定（天数、比例、金额）
4. 更新所有过时的法律引用，精确到具体条文
5. 确保甲乙双方权利义务对等

输出完整的优化后合同（从标题到签署栏），不要省略任何部分："""
        else:
            prompt = f"""请根据以下合同信息和审查发现的问题，生成一份完整的修改后合同文档。

【合同信息】
{contract_info}

{suggestions_section}

【要求】
1. 生成一份完整的合同文档，包含所有必要的条款
2. 将上述修改建议融入到合同条款中
3. 使用专业、准确的法律术语
4. 保持合同的整体结构和意图
5. 符合中国法律法规
6. 使用Markdown格式输出
7. 不要包含任何已修改标记或修改说明部分
8. 不要添加开场白，直接输出合同正文

请直接输出完整的合同文档内容："""
        
        try:
            timeout_val = 180.0 if has_original else 90.0
            max_tokens_val = 16000 if has_original else 8000
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": """你是一位拥有20年执业经验的资深合同律师，曾就职于顶级律所，精通中国《民法典》合同编、《公司法》、《劳动法》、《劳动合同法》、《社会保险法》及司法解释。

你的任务：基于原始合同全文和专业审查发现的具体问题，输出一份法律风险最低、条款最完善、权利义务最对等的合同文本。

## 你的优势
你同时拥有：(1) 原始合同全文 (2) 专业审查发现的具体问题清单。这使你比普通AI修改更专业——审查意见确保你不遗漏关键风险点，你需要在解决所有审查问题的基础上，进一步主动发现并修复审查未覆盖的问题。

## 修订标准（每一条都必须达到）

### 一、审查问题——100%覆盖
- 审查发现的每一个问题都必须在修改后的合同中得到实质性解决
- 不是表面改几个词，而是从根本上消除风险（如：审查说"单方调岗权过大"→不是加"协商"就完事，而是明确调岗条件、程序、补偿机制）

### 二、条款完整性——参照专业合同标准
无论原合同是否包含，修改后的合同应具备以下条款（按合同类型增减）：
- 合同主体信息（名称、地址、联系方式、统一社会信用代码/身份证号）
- 合同期限与生效条件
- 标的与数量质量
- 价款与支付方式（含发票、税费）
- 双方权利义务（对等表述）
- 保密条款（含期限、范围、违约责任）
- 知识产权归属
- 竞业限制（含补偿标准、期限、违约金）
- 违约责任（具体化、量化、对等）
- 不可抗力
- 合同变更与解除（含法定解除权、约定解除条件、补偿机制）
- 争议解决（协商前置→仲裁/诉讼，明确管辖机构）
- 通知与送达（含变更通知义务、送达方式、送达确认）
- 合同份数与保管
- 签署栏（双方签字、日期、盖章）

### 三、法律依据——精准到条文
- 引用法律必须精确到具体条文（如"依据《民法典》第五百八十五条"而非笼统的"依据《民法典》"）
- 已废止法律必须更新：《合同法》《民法通则》→《民法典》；《经济合同法》→《民法典》
- 涉及劳动关系的引用《劳动合同法》《社会保险法》《工伤保险条例》等

### 四、条款细化——从模糊到具体
- "合理期限" → 具体天数（如"15个工作日"）
- "重大损失" → 量化标准（如"损失金额超过合同总额10%"）
- "相关业务" → 具体业务范围描述
- "适当补偿" → 具体计算方式或比例

### 五、权利义务对等
- 删除单方任意解除权 → 改为双方协商解除+法定解除条件
- 单方变更权 → 协商一致+书面确认
- 单方违约金 → 双向违约金对等
- 免责条款 → 限定范围+通知义务

### 六、格式与表述
- 使用正式法律文书用语
- 条款编号连续（第一条、第二条……）
- 每条开头标注条款主题（如"第三条 工作内容及地点"）
- Markdown格式：# 合同标题，## 条款标题

## 输出要求
- 直接输出合同正文，从标题到签署栏
- 不要开场白、不要修改说明、不要标注"已修改"
- 完整输出，不省略任何条款"""
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.2,
                        "max_tokens": max_tokens_val
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    return content
                else:
                    print(f"AI API返回错误: {response.status_code}")
                    return self._rewrite_with_rules(contract, suggestions_to_apply)
                    
        except Exception as e:
            print(f"AI重写合同失败: {str(e)}")
            return self._rewrite_with_rules(contract, suggestions_to_apply)
    
    def _rewrite_with_rules(
        self,
        contract: Contract,
        suggestions_to_apply: List[ModificationSuggestion]
    ) -> str:
        """使用规则引擎生成修改后合同（降级方案）。P3: 优先使用合同类型模板。"""
        return self._generate_from_template_with_type(contract, suggestions_to_apply)

    # === P3: 合同模板库集成 ===
    _TEMPLATE_MAP = {
        "procurement": "01-procurement.md",
        "sales": "02-sales.md",
        "outsourcing": "03-outsourcing.md",
        "equipment": "04-equipment.md",
        "lease": "05-lease.md",
        "power_supply": "06-power_supply.md",
        "nda": "07-nda.md",
        "service": "08-service.md",
        "construction": "09-construction.md",
        "labor": "10-labor.md",
        "other": "11-general.md",
    }
    _TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "contract_templates")

    def _load_template_by_type(self, contract_type: str) -> str:
        """根据合同类型加载模板内容"""
        import os
        type_key = contract_type or "other"
        if type_key == "other":
            return None
        filename = self._TEMPLATE_MAP.get(type_key)
        if not filename:
            return None
        filepath = os.path.join(self._TEMPLATE_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def _generate_from_template_with_type(self, contract, suggestions_to_apply) -> str:
        """使用合同类型模板生成修改后合同"""
        contract_type = ""
        try:
            contract_type = contract.contract_type.value if contract.contract_type else ""
        except Exception:
            contract_type = str(contract.contract_type or "")

        template = self._load_template_by_type(contract_type)
        if not template:
            return self._generate_from_template(contract, suggestions_to_apply)

        result = template
        suggestion_clauses = []
        clause_num = 1
        for s in suggestions_to_apply:
            text = s.suggested_text or ""
            if len(text) < 20:
                text = self._generate_default_suggestion(s.clause or "", s.original_text or "")
            if text:
                suggestion_clauses.append(f"第{_cn_clause_num(clause_num)}条 {s.clause}\n\n{text}\n")
                clause_num += 1

        suggestions_block = "\n".join(suggestion_clauses)
        if suggestions_block:
            insert_idx = -1
            for marker in ["甲方（盖章）", "甲方（签字", "甲方(盖章)", "甲方(签字", "签署"]:
                idx = result.find(marker)
                if idx > 0:
                    insert_idx = idx
                    break
            supplement = f"\n## 补充条款\n\n{suggestions_block}\n\n"
            if insert_idx > 0:
                result = result[:insert_idx] + supplement + result[insert_idx:]
            else:
                result += f"\n\n## 补充条款\n\n{suggestions_block}\n"

        return result

    def _generate_from_template(self, contract, suggestions_to_apply) -> str:
        """没有模板匹配时的默认生成"""
        lines = [
            f"# {contract.title or '合同'}",
            "",
            f"合同编号：{contract.contract_no or '待填写'}",
            f"甲方：{contract.party_a or '待填写'}",
            f"乙方：{contract.party_b or '待填写'}",
            f"合同金额：{contract.amount or '待填写'} {contract.currency or 'CNY'}",
            f"签订日期：{contract.sign_date or '待填写'}",
            f"有效期：{contract.effective_date or '待填写'} 至 {contract.expiry_date or '待填写'}",
            "",
            f"第一条 合同目的",
            f"本合同旨在明确甲乙双方在{contract.title or '本'}项目中的权利和义务。",
            "",
            f"第二条 合同金额与支付",
            f"合同总金额为{contract.amount or '待填写'}{contract.currency or 'CNY'}。",
            "",
        ]
        clause_num = 3
        for s in suggestions_to_apply:
            lines.append(f"第{_cn_clause_num(clause_num)}条 {s.clause}")
            lines.append("")
            text = s.suggested_text or ""
            if len(text) < 20:
                text = self._generate_default_suggestion(s.clause or "", s.original_text or "")
            lines.append(text)
            lines.append("")
            clause_num += 1
        lines.append(f"第{_cn_clause_num(clause_num)}条 违约责任")
        lines.append("任何一方违反本合同约定的，应承担违约责任，赔偿对方因此遭受的损失。")
        lines.append("")
        lines.append(f"第{_cn_clause_num(clause_num + 1)}条 争议解决")
        lines.append("因本合同引起的或与本合同有关的任何争议，双方应友好协商解决；协商不成的，提交甲方所在地人民法院诉讼解决。")
        lines.append("")
        lines.append(f"第{_cn_clause_num(clause_num + 2)}条 其他")
        lines.append("本合同一式两份，甲乙双方各执一份，具有同等法律效力。")
        lines.append("")
        return "\n".join(lines)

    async def _get_next_version(self, db: AsyncSession, contract_id: int) -> int:
        """获取下一个版本号"""
        result = await db.execute(
            select(ContractVersion)
            .where(ContractVersion.contract_id == contract_id)
            .order_by(ContractVersion.version_no.desc())
            .limit(1)
        )
        latest_version = result.scalar_one_or_none()
        return (latest_version.version_no + 1) if latest_version else 1


# 全局实例
contract_modifier = ContractModifier()


class VersionComparer:
    """版本对比器"""
    
    async def compare_versions(
        self,
        db: AsyncSession,
        contract_id: int,
        version1_id: int,
        version2_id: int
    ) -> Dict[str, Any]:
        """对比两个版本的差异"""
        # 获取两个版本
        version1 = await db.get(ContractVersion, version1_id)
        version2 = await db.get(ContractVersion, version2_id)
        
        if not version1 or not version2:
            raise ValueError("版本不存在")
        
        # 获取合同信息
        contract = await db.get(Contract, contract_id)
        
        return {
            "contract_id": contract_id,
            "contract_title": contract.title if contract else "",
            "version1": {
                "id": version1.id,
                "version_no": version1.version_no,
                "change_summary": version1.change_summary,
                "created_at": version1.created_at.isoformat() if version1.created_at else None
            },
            "version2": {
                "id": version2.id,
                "version_no": version2.version_no,
                "change_summary": version2.change_summary,
                "created_at": version2.created_at.isoformat() if version2.created_at else None
            },
            "diff": self._generate_diff(
                version1.change_summary or "",
                version2.change_summary or ""
            )
        }
    
    def _generate_diff(self, text1: str, text2: str) -> List[Dict[str, Any]]:
        """生成文本差异"""
        import difflib
        
        diff = list(difflib.unified_diff(
            text1.splitlines(keepends=True),
            text2.splitlines(keepends=True),
            fromfile="版本1",
            tofile="版本2",
            lineterm=""
        ))
        
        result = []
        for line in diff:
            if line.startswith("+++"):
                continue
            elif line.startswith("---"):
                continue
            elif line.startswith("@@"):
                result.append({"type": "header", "content": line})
            elif line.startswith("+"):
                result.append({"type": "add", "content": line[1:]})
            elif line.startswith("-"):
                result.append({"type": "remove", "content": line[1:]})
            else:
                result.append({"type": "same", "content": line})
        
        return result


# 全局实例
version_comparer = VersionComparer()

def _build_examples_block(findings: List[Dict]) -> str:
    """从风险规则引擎构建反例/正例参考块"""
    try:
        from app.services.risk_rules_engine import INDUSTRY_RISK_RULES
    except ImportError:
        return ""

    examples = []
    for finding in findings:
        finding_text = (finding.get("content", "") + " " + finding.get("category", "")).lower()
        for rule in INDUSTRY_RISK_RULES:
            rule_name = rule.get("name", "")
            if rule_name in finding_text or any(kw in finding_text for kw in rule_name.split() if len(kw) > 1):
                ex = rule.get("example_bad")
                gx = rule.get("example_good")
                if ex and gx:
                    examples.append({
                        "rule": f"{rule['id']} {rule_name}",
                        "example_bad": ex,
                        "example_good": gx,
                    })
                    break

    if not examples:
        return ""

    lines = ["\n## 📖 反例参考 (同类条款常见错误 vs 推荐写法)"]
    for ex in examples:
        lines.append(f"\n### {ex['rule']}")
        lines.append(f"❌ 反例: {ex['example_bad']}")
        lines.append(f"✅ 正例: {ex['example_good']}")
    return "\n".join(lines)
