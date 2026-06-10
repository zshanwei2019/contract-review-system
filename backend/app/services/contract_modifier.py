"""
合同自动修改服务
根据AI审查发现生成修改建议并支持一键应用
"""
import json
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.contract import Contract, ContractVersion
from app.models.review import ReviewTask, ReviewOpinion
from app.core.config import settings


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
        
        prompt = self._build_modification_prompt(contract, findings)
        
        async with httpx.AsyncClient(timeout=60.0) as client:
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
                            "content": """你是一位专业的法律顾问，擅长合同条款修改。
请根据审查发现，为每个问题生成具体的修改建议。

修改建议应该：
1. 保持合同的整体结构和意图
2. 使用专业、准确的法律术语
3. 降低合同风险，保护委托方利益
4. 符合中国法律法规

返回JSON格式的修改建议数组。"""
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000
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
                    suggestions_data = json.loads(json_match.group())
                else:
                    suggestions_data = json.loads(content)
                
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
    
    def _build_modification_prompt(self, contract: Contract, findings: List[Dict]) -> str:
        """构建修改建议提示词"""
        return f"""请根据以下审查发现，为合同生成修改建议。

合同信息：
- 合同名称：{contract.title}
- 合同类型：{contract.contract_type.value if contract.contract_type else '未指定'}
- 甲方：{contract.party_a or '未指定'}
- 乙方：{contract.party_b or '未指定'}
- 金额：{contract.amount or '未指定'} {contract.currency or 'CNY'}

审查发现的问题：
{json.dumps(findings, ensure_ascii=False, indent=2)}

请为每个问题生成具体的修改建议，返回JSON格式：
[
  {{
    "finding_id": "审查发现ID",
    "clause": "涉及的条款名称",
    "original_text": "原始文本（如果是替换类型）",
    "suggested_text": "建议修改后的文本",
    "modification_type": "replace/insert/delete/rewrite",
    "priority": "critical/high/medium/low",
    "reason": "修改理由",
    "legal_basis": "法律依据",
    "risk_if_not_modified": "不修改的风险"
  }}
]"""
    
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
            suggested_text = suggestion if suggestion else self._generate_default_suggestion(category, content)
            
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
        """生成默认修改建议"""
        suggestions_map = {
            "违约责任": "建议明确违约责任条款，包括违约金计算方式、赔偿范围和上限。",
            "付款条件": "建议明确付款条件，包括付款时间、付款方式、发票要求等。",
            "交付条款": "建议明确交付条款，包括交付时间、地点、验收标准和程序。",
            "知识产权": "建议明确知识产权归属，包括背景知识产权和前景知识产权的划分。",
            "保密条款": "建议明确保密义务的范围、期限和例外情况。",
            "争议解决": "建议明确争议解决方式和管辖法院/仲裁机构。",
            "合同期限": "建议明确合同期限、续约条件和提前终止条款。",
            "质量标准": "建议明确质量标准、验收程序和不合格处理方式。",
        }
        
        for key, suggestion in suggestions_map.items():
            if key in category:
                return suggestion
        
        return "建议修改此条款以降低合同风险，保护委托方利益。"
    
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
        
        # 获取修改建议（从审查发现中获取）
        result = await db.execute(
            select(ReviewTask)
            .where(ReviewTask.contract_id == contract_id)
            .order_by(ReviewTask.created_at.desc())
            .limit(1)
        )
        review_task = result.scalar_one_or_none()
        
        if not review_task:
            raise ValueError(f"合同 {contract_id} 没有审查记录")
        
        # 生成修改建议
        suggestions = await self.generate_modification_suggestions(db, contract_id)
        
        # 过滤出要应用的建议
        suggestions_to_apply = [s for s in suggestions if s.id in suggestion_ids]
        
        if not suggestions_to_apply:
            raise ValueError("没有找到要应用的修改建议")
        
        # 更新合同描述，添加修改记录
        modification_summary = []
        for suggestion in suggestions_to_apply:
            modification_summary.append(
                f"[{suggestion.clause}] {suggestion.reason}"
            )
            suggestion.applied = True
        
        # 更新合同信息
        if contract.description:
            contract.description += "\n\n--- 修改记录 ---\n" + "\n".join(modification_summary)
        else:
            contract.description = "--- 修改记录 ---\n" + "\n".join(modification_summary)
        
        # 创建新版本
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
        
        return ModificationResult(
            contract_id=contract.id,
            suggestions=suggestions,
            applied_count=len(suggestions_to_apply),
            total_suggestions=len(suggestions),
            version_id=version.id
        )
    
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
