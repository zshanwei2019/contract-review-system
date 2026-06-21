"""
条款依赖图 + 跨条款一致性校验
- 构建条款间引用/依赖/冲突关系图
- 检测缺失引用、金额不一致、日期矛盾、定义冲突等
- 集成到条款级审查流程中
"""
import re
import logging
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============== 数据模型 ==============

class EdgeType(str, Enum):
    REFERENCE = "reference"       # A 引用 B
    DEPENDENCY = "dependency"     # A 依赖 B (B 不存在则 A 无效)
    CONFLICT = "conflict"         # A 与 B 冲突
    DUPLICATE = "duplicate"       # A 与 B 重复定义


class IssueSeverity(str, Enum):
    CRITICAL = "critical"   # 可能导致合同无效
    HIGH = "high"           # 重大风险
    MEDIUM = "medium"       # 中等风险
    LOW = "low"             # 轻微问题


@dataclass
class ClauseNode:
    """条款节点"""
    index: int
    title: str
    content: str
    clause_type: str = "unknown"
    extracted_amounts: List[Dict] = field(default_factory=list)  # [{value, currency, context}]
    extracted_dates: List[Dict] = field(default_factory=list)    # [{date, type, context}]
    extracted_parties: List[str] = field(default_factory=list)
    extracted_definitions: Dict[str, str] = field(default_factory=dict)  # {term: definition}
    references: List[int] = field(default_factory=list)  # 引用的条款编号


@dataclass
class ClauseEdge:
    """条款间关系边"""
    source: int
    target: int
    edge_type: EdgeType
    description: str
    severity: IssueSeverity = IssueSeverity.MEDIUM
    evidence: str = ""  # 原文证据


@dataclass
class ConsistencyIssue:
    """一致性问题"""
    issue_id: str
    issue_type: str  # missing_ref / amount_mismatch / date_conflict / definition_conflict / term_conflict / logical_gap
    severity: IssueSeverity
    title: str
    description: str
    related_clauses: List[int] = field(default_factory=list)
    suggestion: str = ""
    evidence: List[str] = field(default_factory=list)  # 原文摘录


@dataclass
class DependencyReport:
    """依赖分析报告"""
    total_clauses: int
    nodes: List[ClauseNode] = field(default_factory=list)
    edges: List[ClauseEdge] = field(default_factory=list)
    issues: List[ConsistencyIssue] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)


# ============== 条款依赖图构建 ==============

class ClauseDependencyGraph:
    """条款依赖图"""

    # 引用模式: "按照第X条" / "详见第X条" / "参照第X条" / "如第X条所述"
    REFERENCE_PATTERNS = [
        r'(?:按照|根据|依照|参照|详见|参见|见|如|依据|适用)\s*第\s*([一二三四五六七八九十百千\d]+)\s*条',
        r'第\s*([一二三四五六七八九十百千\d]+)\s*条\s*(?:的?\s*约定|所述|规定)',
        r'(?:前述|上述|前款|上款)\s*(?:第\s*([一二三四五六七八九十百千\d]+)\s*条)?',
        r'(?:以下\s*简称\s*|定义\s*见\s*)第\s*([一二三四五六七八九十百千\d]+)\s*条',
    ]

    # 金额提取模式
    AMOUNT_PATTERNS = [
        r'(?:人民币|￥|¥|RMB)\s*[\d,]+\.?\d*\s*(?:万|元|万元|亿)?',
        r'[\d,]+\.?\d*\s*(?:万|元|万元|亿)\s*(?:人民币|￥|¥|RMB)?',
        r'(?:金额|总价|价款|费用|报酬|租金|货款|违约金|赔偿|罚款)\s*[：:]\s*[\d,]+\.?\d*\s*(?:万|元|万元|亿)?',
        r'(?:金额|总价|价款|费用|报酬|租金|货款)\s*(?:为|共计|合计|总计)\s*[\d,]+\.?\d*\s*(?:万|元|万元|亿)?',
    ]

    # 日期提取模式
    DATE_PATTERNS = [
        r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
        r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        r'(?:自|从|于)\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
        r'(?:期限|有效期|履行期|交付期)\s*[：:]\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
    ]

    # 定义模式: "X 是指/指/系指/即"
    DEFINITION_PATTERN = r'(?:["""])([^"""]+)(?:["""])\s*(?:是指|指|系指|即|为)\s*(.+?)(?:[。；;]|$)'

    # 中文数字映射
    CN_NUM_MAP = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
        '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
        '二十一': 21, '二十二': 22, '二十三': 23, '二十四': 24, '二十五': 25,
        '二十六': 26, '二十七': 27, '二十八': 28, '二十九': 29, '三十': 30,
    }

    def __init__(self):
        self.nodes: Dict[int, ClauseNode] = {}
        self.edges: List[ClauseEdge] = []
        self.issues: List[ConsistencyIssue] = []
        self._issue_counter = 0

    def _next_issue_id(self) -> str:
        self._issue_counter += 1
        return f"CC-{self._issue_counter:03d}"

    def build(self, clauses: List[Dict]) -> DependencyReport:
        """
        从条款列表构建依赖图
        clauses: [{"index": 1, "title": "...", "content": "..."}]
        """
        if not clauses:
            return DependencyReport(total_clauses=0)

        # Step 1: 创建节点 + 提取信息
        for c in clauses:
            node = ClauseNode(
                index=c["index"],
                title=c.get("title", f"第{c['index']}条"),
                content=c.get("content", ""),
                clause_type=c.get("clause_type", "unknown"),
            )
            self._extract_node_info(node)
            self.nodes[node.index] = node

        # Step 2: 构建引用边
        self._build_reference_edges()

        # Step 3: 检测缺失引用
        self._check_missing_references()

        # Step 4: 检测金额不一致
        self._check_amount_consistency()

        # Step 5: 检测日期矛盾
        self._check_date_consistency()

        # Step 6: 检测定义冲突
        self._check_definition_conflicts()

        # Step 7: 检测逻辑缺口 (有依赖但缺条款)
        self._check_logical_gaps()

        # Step 8: 检测条款冲突
        self._check_term_conflicts()

        # 生成摘要
        summary = {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "total_issues": len(self.issues),
            "by_severity": {
                "critical": sum(1 for i in self.issues if i.severity == IssueSeverity.CRITICAL),
                "high": sum(1 for i in self.issues if i.severity == IssueSeverity.HIGH),
                "medium": sum(1 for i in self.issues if i.severity == IssueSeverity.MEDIUM),
                "low": sum(1 for i in self.issues if i.severity == IssueSeverity.LOW),
            },
            "by_type": {},
        }
        for i in self.issues:
            summary["by_type"][i.issue_type] = summary["by_type"].get(i.issue_type, 0) + 1

        return DependencyReport(
            total_clauses=len(self.nodes),
            nodes=list(self.nodes.values()),
            edges=self.edges,
            issues=self.issues,
            summary=summary,
        )

    def _cn_to_int(self, cn: str) -> int:
        """中文数字转整数"""
        return self.CN_NUM_MAP.get(cn, int(cn) if cn.isdigit() else 0)

    def _extract_node_info(self, node: ClauseNode):
        """从条款内容提取结构化信息"""
        content = node.content

        # 提取金额
        for pattern in self.AMOUNT_PATTERNS:
            for m in re.finditer(pattern, content):
                ctx_start = max(0, m.start() - 20)
                ctx_end = min(len(content), m.end() + 30)
                node.extracted_amounts.append({
                    "value": m.group(),
                    "context": content[ctx_start:ctx_end].strip(),
                })

        # 提取日期
        for pattern in self.DATE_PATTERNS:
            for m in re.finditer(pattern, content):
                ctx_start = max(0, m.start() - 15)
                ctx_end = min(len(content), m.end() + 20)
                node.extracted_dates.append({
                    "date": m.group(1) if m.lastindex else m.group(),
                    "context": content[ctx_start:ctx_end].strip(),
                })

        # 提取定义
        for m in re.finditer(self.DEFINITION_PATTERN, content):
            term = m.group(1).strip()
            definition = m.group(2).strip()[:100]
            node.extracted_definitions[term] = definition

        # 提取引用
        for pattern in self.REFERENCE_PATTERNS:
            for m in re.finditer(pattern, content):
                ref_num = self._cn_to_int(m.group(1))
                if ref_num > 0 and ref_num != node.index:
                    node.references.append(ref_num)

        # 去重引用
        node.references = list(set(node.references))

    def _build_reference_edges(self):
        """构建引用关系边"""
        for node in self.nodes.values():
            for ref_idx in node.references:
                edge = ClauseEdge(
                    source=node.index,
                    target=ref_idx,
                    edge_type=EdgeType.REFERENCE,
                    description=f"第{node.index}条引用第{ref_idx}条",
                    severity=IssueSeverity.LOW,
                )
                self.edges.append(edge)

    def _check_missing_references(self):
        """检测引用不存在的条款"""
        existing_indices = set(self.nodes.keys())
        for node in self.nodes.values():
            for ref_idx in node.references:
                if ref_idx not in existing_indices:
                    # 找到原文证据
                    evidence = []
                    for pattern in self.REFERENCE_PATTERNS:
                        for m in re.finditer(pattern, node.content):
                            if self._cn_to_int(m.group(1)) == ref_idx:
                                ctx = node.content[max(0, m.start()-20):min(len(node.content), m.end()+20)]
                                evidence.append(ctx.strip())
                                break

                    issue = ConsistencyIssue(
                        issue_id=self._next_issue_id(),
                        issue_type="missing_ref",
                        severity=IssueSeverity.HIGH,
                        title=f"引用不存在的条款",
                        description=f"第{node.index}条「{node.title}」引用了第{ref_idx}条，但该条款不存在",
                        related_clauses=[node.index],
                        suggestion=f"请检查引用编号是否正确，或补充第{ref_idx}条内容",
                        evidence=evidence[:3],
                    )
                    self.issues.append(issue)

    def _check_amount_consistency(self):
        """检测金额不一致"""
        # 收集所有金额
        all_amounts = []
        for node in self.nodes.values():
            for amt in node.extracted_amounts:
                all_amounts.append({
                    "clause_index": node.index,
                    "clause_title": node.title,
                    "value": amt["value"],
                    "context": amt["context"],
                })

        def parse_amount(text: str) -> Optional[float]:
            """解析金额文本为数值(元)"""
            nums = re.findall(r'[\d,]+\.?\d*', text)
            if not nums:
                return None
            val = float(nums[0].replace(',', ''))
            if '万' in text:
                val *= 10000
            if '亿' in text:
                val *= 100000000
            return val

        # 找总价/合计类金额 vs 分项金额
        total_amounts = [a for a in all_amounts if any(kw in a["context"] for kw in ['总价', '合计', '总计', '总额', '合同金额'])]
        detail_amounts = [a for a in all_amounts if a not in total_amounts]

        seen_pairs = set()

        # 检查两个"总价"类金额是否冲突
        for i in range(len(total_amounts)):
            for j in range(i+1, len(total_amounts)):
                a1, a2 = total_amounts[i], total_amounts[j]
                v1, v2 = parse_amount(a1["value"]), parse_amount(a2["value"])
                if v1 and v2 and abs(v1 - v2) > 0.01:
                    # 检查是否是百分比关系 (如 90% of total)
                    ctx = a2.get("context", "")
                    pct_match = re.search(r'(\d+)\s*%', ctx)
                    if pct_match:
                        pct = float(pct_match.group(1)) / 100
                        if abs(v2 - v1 * pct) < 1:
                            continue  # 是百分比关系，不算冲突

                    pair_key = tuple(sorted([a1["clause_index"], a2["clause_index"]]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    issue = ConsistencyIssue(
                        issue_id=self._next_issue_id(),
                        issue_type="amount_mismatch",
                        severity=IssueSeverity.HIGH,
                        title="合同金额不一致",
                        description=f"第{a1['clause_index']}条金额({a1['value']})与第{a2['clause_index']}条金额({a2['value']})不一致",
                        related_clauses=[a1["clause_index"], a2["clause_index"]],
                        suggestion="请核实合同总金额，确保各处金额一致",
                        evidence=[a1["context"], a2["context"]],
                    )
                    self.issues.append(issue)

    def _check_date_consistency(self):
        """检测日期矛盾"""
        # 收集所有日期
        all_dates = []
        for node in self.nodes.values():
            for d in node.extracted_dates:
                all_dates.append({
                    "clause_index": node.index,
                    "clause_title": node.title,
                    "date": d["date"],
                    "context": d["context"],
                })

        def parse_date(text: str) -> Optional[str]:
            """统一为 YYYY-MM-DD"""
            m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
            if m:
                return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', text)
            if m:
                return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            return None

        def classify_date(ctx: str) -> str:
            """分类日期类型: start/end/unknown"""
            # "自...至..." 模式: 前一个是start, 后一个是end
            range_match = re.search(r'自.*?(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?至.*?(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)', ctx)
            if range_match:
                return "range"  # 这是范围, 单独处理
            if any(kw in ctx for kw in ['开始', '起始', '生效', '签订', '签署', '自']):
                return "start"
            if any(kw in ctx for kw in ['结束', '终止', '到期', '截止', '至']):
                return "end"
            return "unknown"

        # 分离开始/结束日期
        start_dates = []
        end_dates = []
        for d in all_dates:
            cls = classify_date(d["context"])
            if cls == "start":
                start_dates.append(d)
            elif cls == "end":
                end_dates.append(d)
            elif cls == "range":
                # 从范围中提取开始和结束
                m = re.search(r'自.*?(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?至.*?(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)', d["context"])
                if m:
                    start_dates.append({**d, "date": m.group(1)})
                    end_dates.append({**d, "date": m.group(2)})

        seen_pairs = set()

        # 检查开始 > 结束
        for sd in start_dates:
            for ed in end_dates:
                s = parse_date(sd["date"])
                e = parse_date(ed["date"])
                if s and e and s > e:
                    pair_key = tuple(sorted([sd["clause_index"], ed["clause_index"]]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    issue = ConsistencyIssue(
                        issue_id=self._next_issue_id(),
                        issue_type="date_conflict",
                        severity=IssueSeverity.CRITICAL,
                        title="合同日期矛盾",
                        description=f"开始日期({sd['date']})晚于结束日期({ed['date']})，合同期限逻辑错误",
                        related_clauses=[sd["clause_index"], ed["clause_index"]],
                        suggestion="请核实合同起止日期",
                        evidence=[sd["context"], ed["context"]],
                    )
                    self.issues.append(issue)

    def _check_definition_conflicts(self):
        """检测定义冲突: 同一术语在不同条款有不同定义"""
        all_defs: Dict[str, List[Tuple[int, str, str]]] = {}
        for node in self.nodes.values():
            for term, definition in node.extracted_definitions.items():
                if term not in all_defs:
                    all_defs[term] = []
                all_defs[term].append((node.index, node.title, definition))

        for term, entries in all_defs.items():
            if len(entries) >= 2:
                # 检查定义是否不同
                defs = [e[2] for e in entries]
                if len(set(defs)) > 1:
                    issue = ConsistencyIssue(
                        issue_id=self._next_issue_id(),
                        issue_type="definition_conflict",
                        severity=IssueSeverity.HIGH,
                        title=f"术语「{term}」定义冲突",
                        description=f"术语「{term}」在多个条款中有不同定义",
                        related_clauses=[e[0] for e in entries],
                        suggestion=f"请统一术语「{term}」的定义，或明确各条款的适用范围",
                        evidence=[f"第{e[0]}条「{e[1]}」: {e[2][:80]}" for e in entries],
                    )
                    self.issues.append(issue)

    def _check_logical_gaps(self):
        """检测逻辑缺口: 有依赖但缺少对应条款"""
        # 常见逻辑依赖模式
        gap_patterns = [
            (r'违约责任', r'违约.*责任|赔偿|违约金'),
            (r'验收标准', r'验收.*标准|验收.*条件|质量.*标准'),
            (r'付款条件', r'付款.*条件|支付.*条件|付款.*方式'),
            (r'保密条款', r'保密|商业秘密|保密义务'),
            (r'争议解决', r'争议.*解决|仲裁|诉讼|管辖'),
            (r'知识产权', r'知识.*产权|专利|商标|著作权'),
            (r'不可抗力', r'不可抗力|force.*majeure'),
            (r'合同解除', r'合同.*解除|解除.*条件|终止.*条件'),
        ]

        full_text = "\n".join([n.content for n in self.nodes.values()])

        for section_name, pattern in gap_patterns:
            # 检查是否引用了但未定义
            ref_pattern = rf'(?:按照|根据|依照|参照|详见|参见|见)\s*{section_name}'
            has_ref = bool(re.search(ref_pattern, full_text))
            has_section = bool(re.search(pattern, full_text))

            if has_ref and not has_section:
                # 找引用位置
                evidence = []
                for node in self.nodes.values():
                    for m in re.finditer(ref_pattern, node.content):
                        evidence.append(f"第{node.index}条: {node.content[max(0,m.start()-20):m.end()+30].strip()}")
                        break

                issue = ConsistencyIssue(
                    issue_id=self._next_issue_id(),
                    issue_type="logical_gap",
                    severity=IssueSeverity.HIGH,
                    title=f"缺少「{section_name}」条款",
                    description=f"合同引用了「{section_name}」，但未找到对应的独立条款",
                    related_clauses=[],
                    suggestion=f"建议补充「{section_name}」条款，明确相关权利义务",
                    evidence=evidence[:3],
                )
                self.issues.append(issue)

    def _check_term_conflicts(self):
        """检测条款间冲突: 同一事项在不同条款有矛盾约定"""
        # 常见冲突模式
        conflict_pairs = [
            (r'违约金.*?([\d.]+)%', r'违约金.*?([\d.]+)%', '违约金比例'),
            (r'质保期.*?(\d+)\s*(?:个?月|年)', r'质保期.*?(\d+)\s*(?:个?月|年)', '质保期限'),
            (r'付款期限.*?(\d+)\s*(?:个?[日月]|天|工作日)', r'付款期限.*?(\d+)\s*(?:个?[日月]|天|工作日)', '付款期限'),
            (r'管辖.*?法院', r'仲裁', '争议解决方式'),
        ]

        for pat1, pat2, label in conflict_pairs:
            results = {}
            for node in self.nodes.values():
                m1 = re.search(pat1, node.content)
                m2 = re.search(pat2, node.content)
                if m1:
                    val = m1.group(1) if m1.lastindex else m1.group()
                    if val not in results:
                        results[val] = []
                    results[val].append((node.index, node.title, m1.group()))
                if m2 and pat2 != pat1:
                    val = m2.group(1) if m2.lastindex else m2.group()
                    if val not in results:
                        results[val] = []
                    results[val].append((node.index, node.title, m2.group()))

            if len(results) > 1:
                clauses_list = []
                evidence_list = []
                for val, entries in results.items():
                    for idx, title, text in entries:
                        clauses_list.append(idx)
                        evidence_list.append(f"第{idx}条「{title}」: {text[:80]}")

                issue = ConsistencyIssue(
                    issue_id=self._next_issue_id(),
                    issue_type="term_conflict",
                    severity=IssueSeverity.HIGH,
                    title=f"{label}冲突",
                    description=f"不同条款对「{label}」的约定不一致",
                    related_clauses=list(set(clauses_list)),
                    suggestion=f"请统一「{label}」的约定，避免歧义",
                    evidence=evidence_list[:5],
                )
                self.issues.append(issue)

    def to_dict(self, report: DependencyReport) -> Dict:
        """转换为可序列化字典"""
        return {
            "total_clauses": report.total_clauses,
            "summary": report.summary,
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "edge_type": e.edge_type.value,
                    "description": e.description,
                    "severity": e.severity.value,
                }
                for e in report.edges
            ],
            "issues": [
                {
                    "issue_id": i.issue_id,
                    "issue_type": i.issue_type,
                    "severity": i.severity.value,
                    "title": i.title,
                    "description": i.description,
                    "related_clauses": i.related_clauses,
                    "suggestion": i.suggestion,
                    "evidence": i.evidence,
                }
                for i in report.issues
            ],
            "nodes": [
                {
                    "index": n.index,
                    "title": n.title,
                    "clause_type": n.clause_type,
                    "references": n.references,
                    "amounts_count": len(n.extracted_amounts),
                    "dates_count": len(n.extracted_dates),
                    "definitions": list(n.extracted_definitions.keys()),
                }
                for n in report.nodes
            ],
        }


def analyze_clause_dependencies(clauses: List[Dict]) -> Dict:
    """便捷函数: 分析条款依赖关系"""
    graph = ClauseDependencyGraph()
    report = graph.build(clauses)
    return graph.to_dict(report)