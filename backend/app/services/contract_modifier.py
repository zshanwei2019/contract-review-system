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
    original_content: Optional[str] = None
    diff_summary: Optional[str] = None


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
        
        try:
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
            print("AI API调用超时，使用规则引擎生成修改建议")
            return self._generate_with_rules(contract, findings)
        except Exception as e:
            print(f"AI API调用失败: {str(e)}")
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
        
        # 使用AI重写合同内容
        modified_content = await self.rewrite_contract_with_ai(contract, suggestions_to_apply)
        
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
        suggestions_to_apply: List[ModificationSuggestion]
    ) -> str:
        """使用AI重写合同内容，应用修改建议"""
        if not self.api_key:
            return self._rewrite_with_rules(contract, suggestions_to_apply)
        
        import httpx
        
        # 构建合同信息
        contract_info = f"""合同名称：{contract.title}
合同类型：{contract.contract_type.value if contract.contract_type else '未指定'}
甲方：{contract.party_a or '未指定'}
乙方：{contract.party_b or '未指定'}
合同金额：{contract.amount or '未指定'} {contract.currency or 'CNY'}
签订日期：{contract.sign_date or '未指定'}
生效日期：{contract.effective_date or '未指定'}
到期日期：{contract.expiry_date or '未指定'}
合同摘要：{contract.description or '无'}"""
        
        # 构建修改建议列表
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
        
        prompt = f"""请根据以下合同信息和修改建议，生成一份完整的修改后合同文档。

【合同信息】
{contract_info}

【需要应用的修改建议】
{suggestions_text}

【要求】
1. 生成一份完整的合同文档，包含所有必要的条款
2. 将上述修改建议融入到合同条款中
3. 使用专业、准确的法律术语
4. 保持合同的整体结构和意图
5. 符合中国法律法规
6. 使用Markdown格式输出
7. 在修改的条款旁边标注 [已修改] 标记
8. 在文档末尾添加"修改说明"部分，列出所有修改内容

请直接输出完整的合同文档内容："""
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
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
                                "content": "你是一位专业的法律顾问，擅长合同起草和修改。请根据提供的信息生成完整的合同文档。"
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
        """使用规则引擎生成修改后合同（降级方案）"""
        lines = [
            f"# {contract.title}",
            "",
            f"**合同编号**：{contract.contract_no or '待填写'}",
            f"**甲方**：{contract.party_a or '待填写'}",
            f"**乙方**：{contract.party_b or '待填写'}",
            f"**合同金额**：{contract.amount or '待填写'} {contract.currency or 'CNY'}",
            f"**签订日期**：{contract.sign_date or '待填写'}",
            f"**有效期**：{contract.effective_date or '待填写'} 至 {contract.expiry_date or '待填写'}",
            "",
            "---",
            "",
            "## 合同条款",
            "",
            "### 第一条 合同目的",
            f"本合同旨在明确甲乙双方在{contract.title}项目中的权利和义务。",
            "",
            "### 第二条 合同金额与支付",
            f"合同总金额为{contract.amount or '待填写'}{contract.currency or 'CNY'}。",
            "",
        ]
        
        # 添加修改后的条款
        clause_num = 3
        for s in suggestions_to_apply:
            lines.append(f"### 第{clause_num}条 {s.clause} **[已修改]**")
            lines.append("")
            lines.append(s.suggested_text)
            lines.append("")
            lines.append(f"> **修改理由**：{s.reason}")
            lines.append(f"> **法律依据**：{s.legal_basis}")
            lines.append("")
            clause_num += 1
        
        # 添加标准条款
        lines.extend([
            f"### 第{clause_num}条 违约责任",
            "任何一方违反本合同约定的，应承担违约责任，赔偿对方因此遭受的损失。",
            "",
            f"### 第{clause_num + 1}条 争议解决",
            "因本合同引起的或与本合同有关的任何争议，双方应友好协商解决；协商不成的，提交甲方所在地人民法院诉讼解决。",
            "",
            f"### 第{clause_num + 2}条 其他",
            "本合同一式两份，甲乙双方各执一份，具有同等法律效力。",
            "",
            "---",
            "",
            "## 修改说明",
            "",
            f"本合同已根据AI审查建议进行了 {len(suggestions_to_apply)} 处修改：",
            "",
        ])
        
        for i, s in enumerate(suggestions_to_apply, 1):
            lines.append(f"{i}. **{s.clause}**：{s.reason}")
        
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
