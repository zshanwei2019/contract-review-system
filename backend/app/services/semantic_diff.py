"""
合同语义比对服务 (Semantic Diff)
- 对比两份合同文本，识别实质性修改 vs 格式调整
- 按条款聚类修改块
- 评估修改的风险影响
"""
import re
import difflib
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    ADDED = "added"           # 新增
    REMOVED = "removed"       # 删除
    MODIFIED = "modified"     # 修改
    FORMATTING = "formatting" # 仅格式调整


class ChangeSeverity(str, Enum):
    CRITICAL = "critical"     # 重大实质性变更
    HIGH = "high"             # 重要变更
    MEDIUM = "medium"         # 一般变更
    LOW = "low"               # 轻微变更
    COSMETIC = "cosmetic"     # 格式/标点


@dataclass
class DiffBlock:
    """一个修改块"""
    block_id: str
    change_type: ChangeType
    severity: ChangeSeverity
    original_text: str = ""
    modified_text: str = ""
    clause_ref: str = ""         # 所在条款
    position: int = 0            # 位置偏移
    summary: str = ""            # 一句话总结
    risk_impact: str = ""        # 风险影响: increased/decreased/unchanged
    key_changes: List[str] = field(default_factory=list)  # 关键变化点


@dataclass
class DiffReport:
    """比对报告"""
    total_blocks: int
    blocks: List[DiffBlock] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)
    risk_changes: List[Dict] = field(default_factory=list)


class SemanticDiff:
    """语义比对引擎"""

    # 实质性修改关键词 (出现这些词的修改更可能是实质性的)
    SUBSTANTIVE_KEYWORDS = [
        '金额', '价格', '价款', '费用', '支付', '付款',
        '期限', '日期', '时间', '交付', '交货',
        '违约', '赔偿', '罚款', '责任', '担保',
        '解除', '终止', '撤销', '变更',
        '管辖', '仲裁', '诉讼', '法律适用',
        '保密', '竞业', '知识产权', '专利',
        '质保', '保修', '验收', '标准',
        '不可抗力', '免责', '保险',
        '自动续约', '排他', '独家', '优先',
    ]

    # 格式修改关键词 (出现这些词的修改更可能是格式调整)
    FORMATTING_KEYWORDS = [
        '甲方', '乙方', '双方', '协商', '同意',
        '根据', '依据', '按照', '依照',
        '特此', '兹', '鉴于', '为此',
        '一式', '份', '各执', '签字', '盖章',
        '通知', '送达', '地址', '联系方式',
        '以下', '上述', '前述', '本协议',
    ]

    # 风险增加模式
    RISK_INCREASE_PATTERNS = [
        (r'(?:增加|提高|上调|上涨)\s*(?:金额|价格|费用|违约金|赔偿|价款)', '金额/费用增加'),
        (r'(?:缩短|减少)\s*(?:期限|时间|天数|工作日)', '期限缩短'),
        (r'(?:扩大|增加)\s*(?:责任|义务|范围)', '责任扩大'),
        (r'(?:删除|取消|移除)\s*(?:质保|保修|验收|检验)', '保护条款删除'),
        (r'(?:自动续约|自动延期|自动展期)', '自动续约风险'),
        (r'(?:单方|单方面)\s*(?:解除|终止|变更|修改)', '单方权利增加'),
        (r'(?:无限|连带|担保)\s*责任', '无限/连带责任'),
        (r'(?:金额|价格|价款|费用|违约金|赔偿).*?(?:增加|提高|上调|上涨)', '金额/费用增加'),
    ]

    # 风险降低模式
    RISK_DECREASE_PATTERNS = [
        (r'(?:减少|降低|下调)\s*(?:金额|价格|费用|违约金)', '金额/费用降低'),
        (r'(?:延长|增加)\s*(?:期限|时间|天数)', '期限延长'),
        (r'(?:增加|补充)\s*(?:质保|保修|验收|检验)', '保护条款增加'),
        (r'(?:删除|取消|移除)\s*(?:自动续约|排他|独家)', '风险条款删除'),
        (r'(?:限制|限定)\s*(?:责任|赔偿|违约金)', '责任限制'),
    ]

    def compare(self, original: str, modified: str,
                original_title: str = "原始版本",
                modified_title: str = "修改版本") -> DiffReport:
        """
        比对两份合同文本
        """
        if not original or not modified:
            return DiffReport(total_blocks=0, summary={"error": "文本为空"})

        # Step 1: 文本级 diff
        raw_diffs = self._text_diff(original, modified)

        # Step 2: 聚类为修改块
        blocks = self._cluster_diffs(raw_diffs, original, modified)

        # Step 3: 分类修改类型
        for block in blocks:
            self._classify_change(block)

        # Step 4: 评估风险影响
        risk_changes = self._assess_risk_impact(blocks)

        # Step 5: 生成摘要
        summary = {
            "original_title": original_title,
            "modified_title": modified_title,
            "total_blocks": len(blocks),
            "by_type": {},
            "by_severity": {},
            "substantive_count": 0,
            "formatting_count": 0,
            "risk_increased": 0,
            "risk_decreased": 0,
            "risk_unchanged": 0,
        }
        for b in blocks:
            summary["by_type"][b.change_type.value] = summary["by_type"].get(b.change_type.value, 0) + 1
            summary["by_severity"][b.severity.value] = summary["by_severity"].get(b.severity.value, 0) + 1
            if b.change_type != ChangeType.FORMATTING:
                summary["substantive_count"] += 1
            else:
                summary["formatting_count"] += 1
            if b.risk_impact == "increased":
                summary["risk_increased"] += 1
            elif b.risk_impact == "decreased":
                summary["risk_decreased"] += 1
            else:
                summary["risk_unchanged"] += 1

        return DiffReport(
            total_blocks=len(blocks),
            blocks=blocks,
            summary=summary,
            risk_changes=risk_changes,
        )

    def _text_diff(self, original: str, modified: str) -> List[Tuple[str, str, str]]:
        """文本级 diff，返回 [(tag, text_a, text_b)]"""
        # 按段落分割
        orig_lines = original.splitlines(keepends=True)
        mod_lines = modified.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, orig_lines, mod_lines)
        diffs = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue
            elif tag == 'replace':
                diffs.append(('replace', ''.join(orig_lines[i1:i2]), ''.join(mod_lines[j1:j2])))
            elif tag == 'delete':
                diffs.append(('delete', ''.join(orig_lines[i1:i2]), ''))
            elif tag == 'insert':
                diffs.append(('insert', '', ''.join(mod_lines[j1:j2])))

        return diffs

    def _cluster_diffs(self, raw_diffs: List[Tuple[str, str, str]],
                       original: str, modified: str) -> List[DiffBlock]:
        """将 diff 聚类为有意义的修改块"""
        blocks = []
        block_id = 0

        for tag, old_text, new_text in raw_diffs:
            block_id += 1
            old_text = old_text.strip()
            new_text = new_text.strip()

            if not old_text and not new_text:
                continue

            # 判断修改类型
            if tag == 'insert':
                change_type = ChangeType.ADDED
            elif tag == 'delete':
                change_type = ChangeType.REMOVED
            else:
                change_type = ChangeType.MODIFIED

            # 找到所在条款
            clause_ref = self._find_clause_ref(old_text or new_text, original)

            # 生成摘要
            summary = self._generate_change_summary(old_text, new_text, change_type)

            block = DiffBlock(
                block_id=f"DIFF-{block_id:03d}",
                change_type=change_type,
                severity=ChangeSeverity.MEDIUM,
                original_text=old_text[:500],
                modified_text=new_text[:500],
                clause_ref=clause_ref,
                summary=summary,
                key_changes=self._extract_key_changes(old_text, new_text),
            )
            blocks.append(block)

        return blocks

    def _find_clause_ref(self, text: str, original: str) -> str:
        """找到文本所在的条款"""
        if not text:
            return ""
        # 在原文中搜索
        pos = original.find(text[:30])
        if pos >= 0:
            # 向前找最近的条款标题
            before = original[:pos]
            m = re.findall(r'(第[一二三四五六七八九十百千\d]+[条章])', before)
            if m:
                return m[-1]
        return ""

    def _generate_change_summary(self, old_text: str, new_text: str,
                                  change_type: ChangeType) -> str:
        """生成修改摘要"""
        if change_type == ChangeType.ADDED:
            preview = new_text[:80].replace('\n', ' ')
            return f"新增: {preview}..."
        elif change_type == ChangeType.REMOVED:
            preview = old_text[:80].replace('\n', ' ')
            return f"删除: {preview}..."
        else:
            # 找出具体变化
            old_preview = old_text[:40].replace('\n', ' ')
            new_preview = new_text[:40].replace('\n', ' ')
            return f"修改: {old_preview} → {new_preview}"

    def _extract_key_changes(self, old_text: str, new_text: str) -> List[str]:
        """提取关键变化点"""
        changes = []

        # 数字变化
        old_nums = re.findall(r'[\d,]+\.?\d*', old_text)
        new_nums = re.findall(r'[\d,]+\.?\d*', new_text)
        if old_nums != new_nums:
            changes.append(f"数值变更: {', '.join(old_nums[:3])} → {', '.join(new_nums[:3])}")

        # 关键词变化
        for kw in self.SUBSTANTIVE_KEYWORDS:
            in_old = kw in old_text
            in_new = kw in new_text
            if in_old and not in_new:
                changes.append(f"移除「{kw}」相关条款")
            elif not in_old and in_new:
                changes.append(f"新增「{kw}」相关条款")

        return changes[:5]

    def _classify_change(self, block: DiffBlock):
        """分类修改: 实质性 vs 格式"""
        combined = block.original_text + block.modified_text

        substantive_score = sum(1 for kw in self.SUBSTANTIVE_KEYWORDS if kw in combined)
        formatting_score = sum(1 for kw in self.FORMATTING_KEYWORDS if kw in combined)

        if substantive_score >= 3:
            block.severity = ChangeSeverity.HIGH
            block.change_type = ChangeType.MODIFIED
        elif substantive_score >= 1:
            block.severity = ChangeSeverity.MEDIUM
        elif formatting_score >= 3 and substantive_score == 0:
            block.change_type = ChangeType.FORMATTING
            block.severity = ChangeSeverity.COSMETIC
        else:
            block.severity = ChangeSeverity.LOW

        # 纯格式调整
        if block.change_type != ChangeType.FORMATTING:
            # 检查是否只是标点/空格变化
            old_clean = re.sub(r'\s+', '', block.original_text)
            new_clean = re.sub(r'\s+', '', block.modified_text)
            if old_clean == new_clean:
                block.change_type = ChangeType.FORMATTING
                block.severity = ChangeSeverity.COSMETIC

    def _assess_risk_impact(self, blocks: List[DiffBlock]) -> List[Dict]:
        """评估修改对风险的影响"""
        risk_changes = []

        for block in blocks:
            if block.change_type == ChangeType.FORMATTING:
                block.risk_impact = "unchanged"
                continue

            combined = block.original_text + block.modified_text
            new_text = block.modified_text

            increase_score = 0
            decrease_score = 0
            increase_reasons = []
            decrease_reasons = []

            for pattern, reason in self.RISK_INCREASE_PATTERNS:
                if re.search(pattern, new_text):
                    increase_score += 1
                    increase_reasons.append(reason)

            for pattern, reason in self.RISK_DECREASE_PATTERNS:
                if re.search(pattern, new_text):
                    decrease_score += 1
                    decrease_reasons.append(reason)

            if increase_score > decrease_score:
                block.risk_impact = "increased"
                block.severity = ChangeSeverity.HIGH if increase_score >= 2 else ChangeSeverity.MEDIUM
            elif decrease_score > increase_score:
                block.risk_impact = "decreased"
            else:
                block.risk_impact = "unchanged"

            if increase_reasons or decrease_reasons:
                risk_changes.append({
                    "block_id": block.block_id,
                    "risk_impact": block.risk_impact,
                    "increase_reasons": increase_reasons,
                    "decrease_reasons": decrease_reasons,
                    "summary": block.summary,
                })

        return risk_changes

    def to_dict(self, report: DiffReport) -> Dict:
        return {
            "total_blocks": report.total_blocks,
            "summary": report.summary,
            "risk_changes": report.risk_changes,
            "blocks": [
                {
                    "block_id": b.block_id,
                    "change_type": b.change_type.value,
                    "severity": b.severity.value,
                    "clause_ref": b.clause_ref,
                    "summary": b.summary,
                    "risk_impact": b.risk_impact,
                    "key_changes": b.key_changes,
                    "original_text": b.original_text[:200],
                    "modified_text": b.modified_text[:200],
                }
                for b in report.blocks
            ],
        }


def compare_contracts(original: str, modified: str,
                      original_title: str = "原始版本",
                      modified_title: str = "修改版本") -> Dict:
    """便捷函数"""
    diff = SemanticDiff()
    report = diff.compare(original, modified, original_title, modified_title)
    return diff.to_dict(report)
