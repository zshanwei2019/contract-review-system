"""
条款级审查服务
将合同拆分为独立条款，逐条进行: 规则引擎检查 + RAG检索 + AI精审
只对高风险条款调AI，低风险条款用规则引擎覆盖
"""
import json
import logging
import asyncio
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

from app.services.clause_segmenter import segment_clauses, analyze_clause_risks, get_clause_summary
from app.services.clause_dependency import analyze_clause_dependencies
from app.services.risk_rules_engine import (
    check_industry_risks, detect_poison_pills, full_risk_analysis,
    INDUSTRY_RISK_RULES, POISON_PILL_PATTERNS
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# 风险阈值: 只有高于此分的条款才调 AI
AI_REVIEW_THRESHOLD = 0.4  # 0-1, 条款风险分 >= 0.4 才调 AI

# AI 审查的 system prompt (条款级)
CLAUSE_REVIEW_SYSTEM_PROMPT = """你是一位拥有15年执业经验的资深合同律师，正在逐条款审查合同。

## 任务
对给定的单个条款进行深度风险分析，并给出具体修改建议。

## 分析框架
1. **合法性** — 是否违反《民法典》及相关法律的强制性规定
2. **对等性** — 甲乙双方权利义务是否平衡
3. **确定性** — 是否存在模糊表述、歧义
4. **可执行性** — 约定是否可实际操作
5. **风险传导** — 是否可能引发连锁风险

## 输出要求 (JSON)
{
  "risk_level": "high/medium/low",
  "risk_score": 0-100,
  "issues": [
    {
      "issue_type": "合法性/对等性/确定性/可执行性/风险传导",
      "description": "问题描述（引用条款原文）",
      "severity": "high/medium/low",
      "suggestion": "修改后的完整条款文本（不是'建议明确XX'，而是直接给出修改后文本）",
      "legal_basis": "精确法条引用（如《民法典》第五百八十五条第二款）",
      "risk_if_not_modified": "不修改的具体后果"
    }
  ],
  "overall_assessment": "条款整体评价（50字以内）"
}

## 关键原则
- 只报告有问题的点，不要对正常条款凑数
- 修改建议必须给出完整替换文本
- 法条必须精确到条/款
- high = 可能导致合同无效/重大损失；medium = 争议风险；low = 优化建议
"""


@dataclass
class ClauseReviewResult:
    """单条款审查结果"""
    clause_index: int
    clause_title: str
    clause_content: str
    clause_type: str  # 条款分类
    rule_risks: List[Dict] = field(default_factory=list)  # 规则引擎检出
    poison_pills: List[Dict] = field(default_factory=list)  # 毒丸条款
    ai_review: Optional[Dict] = None  # AI 审查结果
    rag_references: List[Dict] = field(default_factory=list)  # RAG 检索参考
    combined_risk_level: str = "low"  # 综合风险等级
    combined_risk_score: float = 0.0  # 综合风险分 0-1
    suggestions: List[Dict] = field(default_factory=list)  # 合并后的修改建议


@dataclass
class ContractClauseReview:
    """合同条款级审查结果"""
    contract_id: int
    total_clauses: int
    clauses: List[ClauseReviewResult] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)
    ai_calls_made: int = 0  # 实际调 AI 的次数
    ai_calls_saved: int = 0  # 节省的 AI 调用次数


class ClauseReviewService:
    """条款级审查服务"""

    def __init__(self):
        self._rag = None

    def _get_rag(self):
        if self._rag is None:
            try:
                from app.services.contract_rag import get_rag
                self._rag = get_rag()
            except Exception as e:
                logger.warning(f"RAG 服务不可用: {e}")
        return self._rag

    async def review_contract_by_clauses(
        self,
        contract_text: str,
        contract_type: str = "all",
        contract_id: Optional[int] = None,
        use_ai: bool = True,
        use_rag: bool = True,
    ) -> ContractClauseReview:
        """
        条款级审查主入口
        1. 条款分割
        2. 规则引擎 + 毒丸检测 (全量)
        3. RAG 检索 (高风险条款)
        4. AI 精审 (仅高风险条款)
        5. 合并结果
        """
        # Step 1: 条款分割
        clauses = segment_clauses(contract_text)
        if not clauses:
            logger.warning("条款分割结果为空")
            return ContractClauseReview(
                contract_id=contract_id or 0,
                total_clauses=0,
                summary={"error": "条款分割失败"},
            )

        logger.info(f"条款分割完成: {len(clauses)} 个条款")

        # Step 2: 逐条规则引擎检查
        results = []
        for clause in clauses:
            result = ClauseReviewResult(
                clause_index=clause["index"],
                clause_title=clause["title"],
                clause_content=clause["content"],
                clause_type=clause.get("clause_type", "未知"),
            )

            # 规则引擎检查
            rule_risks = check_industry_risks(clause["content"], contract_type)
            result.rule_risks = rule_risks

            # 毒丸条款检测
            poison_pills = detect_poison_pills(clause["content"])
            result.poison_pills = poison_pills

            # 计算条款风险分
            max_rule_sev = max([r["severity"] for r in rule_risks] + [0])
            max_pp_sev = max([p["severity"] for p in poison_pills] + [0])
            result.combined_risk_score = max(max_rule_sev, max_pp_sev)
            result.combined_risk_level = (
                "high" if result.combined_risk_score >= 0.7
                else "medium" if result.combined_risk_score >= 0.4
                else "low"
            )

            results.append(result)

        # Step 3: RAG 检索 (对中高风险条款)
        if use_rag:
            rag = self._get_rag()
            if rag:
                for result in results:
                    if result.combined_risk_score >= AI_REVIEW_THRESHOLD:
                        try:
                            ctx = rag.retrieve(
                                result.clause_content,
                                contract_type=contract_type,
                                top_k=3,
                            )
                            if not ctx.is_empty():
                                result.rag_references = [
                                    {
                                        "clause_text": r.clause_text[:200],
                                        "suggestion": r.suggestion_text[:300] if r.suggestion_text else "",
                                        "similarity": f"{r.similarity:.0%}",
                                        "risk_level": r.risk_level,
                                    }
                                    for r in ctx.retrieved
                                ]
                        except Exception as e:
                            logger.warning(f"RAG 检索失败 (条款 {result.clause_index}): {e}")

        # Step 4: AI 精审 (仅高风险条款)
        ai_calls = 0
        ai_saved = 0
        if use_ai and settings.OPENAI_API_KEY:
            for result in results:
                if result.combined_risk_score >= AI_REVIEW_THRESHOLD:
                    try:
                        ai_result = await self._ai_review_clause(
                            result.clause_title,
                            result.clause_content,
                            result.rag_references,
                            result.rule_risks,
                            result.poison_pills,
                        )
                        result.ai_review = ai_result
                        ai_calls += 1

                        # 合并 AI 建议到 suggestions
                        if ai_result and ai_result.get("issues"):
                            for issue in ai_result["issues"]:
                                result.suggestions.append({
                                    "source": "ai",
                                    "issue_type": issue.get("issue_type", ""),
                                    "description": issue.get("description", ""),
                                    "suggestion": issue.get("suggestion", ""),
                                    "legal_basis": issue.get("legal_basis", ""),
                                    "risk_if_not_modified": issue.get("risk_if_not_modified", ""),
                                    "severity": issue.get("severity", "medium"),
                                })
                    except Exception as e:
                        logger.error(f"AI 审查条款 {result.clause_index} 失败: {e}")
                else:
                    ai_saved += 1

        # 合并规则引擎建议到 suggestions
        for result in results:
            for risk in result.rule_risks:
                result.suggestions.append({
                    "source": "rule_engine",
                    "rule_id": risk["rule_id"],
                    "description": risk["description"],
                    "suggestion": risk["suggestion"],
                    "severity": risk["severity"],
                })
            for pp in result.poison_pills:
                result.suggestions.append({
                    "source": "poison_pill",
                    "pattern_id": pp["pattern_id"],
                    "description": f"毒丸条款: {pp['name']}",
                    "suggestion": f"建议删除或修改此毒丸条款 ({pp['type']})",
                    "severity": pp["severity"],
                })

        # Step 5: 条款依赖分析 + 跨条款一致性校验
        dependency_report = None
        try:
            dependency_report = analyze_clause_dependencies(clauses)
            logger.info(f"依赖分析完成: {dependency_report['summary']['total_issues']} 个一致性问题")
        except Exception as e:
            logger.warning(f"依赖分析失败: {e}")

        # Step 6: 生成摘要
        total = len(results)
        high_count = sum(1 for r in results if r.combined_risk_level == "high")
        medium_count = sum(1 for r in results if r.combined_risk_level == "medium")
        low_count = sum(1 for r in results if r.combined_risk_level == "low")
        total_suggestions = sum(len(r.suggestions) for r in results)

        summary = {
            "total_clauses": total,
            "risk_distribution": {"high": high_count, "medium": medium_count, "low": low_count},
            "total_suggestions": total_suggestions,
            "ai_calls_made": ai_calls,
            "ai_calls_saved": ai_saved,
            "ai_efficiency": f"{ai_saved}/{total} 条款由规则引擎覆盖，{ai_calls} 条款AI精审",
            "high_risk_clauses": [
                {"index": r.clause_index, "title": r.clause_title, "score": r.combined_risk_score}
                for r in results if r.combined_risk_level == "high"
            ],
        }

        # 合并依赖分析结果
        if dependency_report:
            summary["dependency_issues"] = dependency_report["summary"]
            summary["cross_clause_issues"] = dependency_report["issues"]

        return ContractClauseReview(
            contract_id=contract_id or 0,
            total_clauses=total,
            clauses=results,
            summary=summary,
            ai_calls_made=ai_calls,
            ai_calls_saved=ai_saved,
        )

    async def _ai_review_clause(
        self,
        clause_title: str,
        clause_content: str,
        rag_refs: List[Dict],
        rule_risks: List[Dict],
        poison_pills: List[Dict],
    ) -> Optional[Dict]:
        """对单个条款调 AI 精审"""
        import httpx

        # 构建 user prompt
        rag_block = ""
        if rag_refs:
            rag_lines = ["\n## 历史类似条款参考"]
            for i, ref in enumerate(rag_refs, 1):
                rag_lines.append(f"\n### 参考 {i} (相似度 {ref['similarity']})")
                rag_lines.append(f"类似条款: {ref['clause_text']}")
                if ref.get("suggestion"):
                    rag_lines.append(f"修改建议: {ref['suggestion']}")
            rag_block = "\n".join(rag_lines)

        rule_block = ""
        if rule_risks:
            rule_lines = ["\n## 规则引擎检出"]
            for r in rule_risks:
                rule_lines.append(f"- {r['rule_id']} {r['rule_name']}: {r['description']}")
            rule_block = "\n".join(rule_lines)

        pp_block = ""
        if poison_pills:
            pp_lines = ["\n## 毒丸条款检出"]
            for p in poison_pills:
                pp_lines.append(f"- {p['pattern_id']} {p['name']} (类型: {p['type']})")
            pp_block = "\n".join(pp_lines)

        user_prompt = f"""## 待审查条款
**条款标题**: {clause_title}
**条款内容**:
{clause_content}
{rule_block}{pp_block}{rag_block}

请按输出要求返回JSON格式的审查结果。"""

        api_base = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": CLAUSE_REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        ai_text = data["choices"][0]["message"]["content"]

        # 解析 JSON
        text = ai_text.strip()
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
            result = {
                "risk_level": "medium",
                "risk_score": 50,
                "issues": [],
                "overall_assessment": ai_text[:200],
            }

        result.setdefault("risk_level", "medium")
        result.setdefault("risk_score", 50)
        result.setdefault("issues", [])
        result.setdefault("overall_assessment", "")

        return result

    def to_dict(self, review: ContractClauseReview) -> Dict:
        """转换为可序列化的字典"""
        return {
            "contract_id": review.contract_id,
            "total_clauses": review.total_clauses,
            "summary": review.summary,
            "ai_calls_made": review.ai_calls_made,
            "ai_calls_saved": review.ai_calls_saved,
            "clauses": [
                {
                    "clause_index": c.clause_index,
                    "clause_title": c.clause_title,
                    "clause_content": c.clause_content[:500],  # 截断
                    "clause_type": c.clause_type,
                    "rule_risks": c.rule_risks,
                    "poison_pills": c.poison_pills,
                    "ai_review": c.ai_review,
                    "rag_references": c.rag_references,
                    "combined_risk_level": c.combined_risk_level,
                    "combined_risk_score": c.combined_risk_score,
                    "suggestions": c.suggestions,
                }
                for c in review.clauses
            ],
        }


# 单例
_service: Optional[ClauseReviewService] = None

def get_clause_review_service() -> ClauseReviewService:
    global _service
    if _service is None:
        _service = ClauseReviewService()
    return _service
