"""
双语合同审查服务 (Bilingual Contract Review)
- 中英文合同段落对齐
- 双语条款一致性校验（金额/日期/义务）
- 术语翻译一致性检查
- 跨语言风险识别
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BilingualAlignment:
    """双语对齐结果"""
    index: int
    cn_text: str
    en_text: str
    confidence: float
    issues: List[Dict] = field(default_factory=list)


# 常见合同术语中英对照
CONTRACT_TERMS_MAP = {
    "甲方": ["Party A", "First Party"],
    "乙方": ["Party B", "Second Party"],
    "买方": ["Buyer", "Purchaser"],
    "卖方": ["Seller", "Vendor"],
    "出租方": ["Lessor", "Landlord"],
    "承租方": ["Lessee", "Tenant"],
    "违约金": ["liquidated damages", "penalty"],
    "定金": ["deposit", "earnest money"],
    "预付款": ["advance payment", "prepayment"],
    "尾款": ["balance payment", "final payment"],
    "逾期付款": ["late payment", "overdue payment"],
    "滞纳金": ["late fee", "surcharge"],
    "生效日": ["effective date", "commencement date"],
    "终止日": ["termination date", "expiry date"],
    "宽限期": ["grace period", "cure period"],
    "通知期": ["notice period"],
    "不可抗力": ["force majeure"],
    "保密义务": ["confidentiality obligation", "duty of confidentiality"],
    "竞业限制": ["non-compete", "non-competition"],
    "知识产权": ["intellectual property", "IP rights"],
    "损害赔偿": ["damages", "compensation for damages"],
    "连带责任": ["joint and several liability"],
    "仲裁": ["arbitration"],
    "管辖": ["jurisdiction"],
    "适用法律": ["governing law", "applicable law"],
    "争议解决": ["dispute resolution"],
    "变更": ["amendment", "modification"],
    "解除": ["termination", "rescission"],
    "转让": ["assignment", "transfer"],
    "续约": ["renewal", "extension"],
    "可分割性": ["severability"],
    "完整协议": ["entire agreement", "integration clause"],
    "保证": ["warranty", "representation"],
    "赔偿": ["indemnification", "indemnity"],
    "责任限制": ["limitation of liability"],
    "免责": ["disclaimer", "exclusion of liability"],
    "第三方": ["third party"],
    "关联方": ["affiliate", "related party"],
    "书面通知": ["written notice"],
    "重大违约": ["material breach"],
    "根本违约": ["fundamental breach"],
}


def _split_paragraphs(text: str) -> List[str]:
    # 按空行或条款编号分割
    paragraphs = re.split(r'\n\s*\n', text)
    # 如果只有一个段落，尝试按条款编号分割
    if len(paragraphs) <= 1:
        paragraphs = re.split(r'\n(?=(?:第[一二三四五六七八九十百\d]+条|Article\s+\d+|Section\s+\d+|Clause\s+\d+))', text)
    return [p.strip() for p in paragraphs if p.strip() and len(p.strip()) > 10]


def _detect_language(text: str) -> str:
    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    en_chars = len(re.findall(r'[a-zA-Z]', text))
    total = cn_chars + en_chars
    if total == 0:
        return "unknown"
    cn_ratio = cn_chars / total
    if cn_ratio > 0.6:
        return "cn"
    elif cn_ratio < 0.3:
        return "en"
    return "mixed"


def _extract_clause_number(text: str) -> Optional[str]:
    m = re.search(r'第[一二三四五六七八九十百\d]+条', text)
    if m:
        return m.group()
    m = re.search(r'(?:Article|Section|Clause)\s+[\d]+', text, re.IGNORECASE)
    if m:
        return m.group()
    m = re.search(r'^[\d]+(?:\.[\d]+)*\s*[\.、]', text)
    if m:
        return m.group().strip()
    return None


def align_bilingual(cn_text: str, en_text: str) -> List[BilingualAlignment]:
    """中英文段落对齐"""
    cn_paras = _split_paragraphs(cn_text)
    en_paras = _split_paragraphs(en_text)

    cn_clauses = [p for p in cn_paras if _detect_language(p) in ("cn", "mixed")]
    en_clauses = [p for p in en_paras if _detect_language(p) in ("en", "mixed")]

    alignments = []

    # 按条款编号对齐
    cn_by_num = {}
    for p in cn_clauses:
        num = _extract_clause_number(p)
        if num:
            cn_by_num[num] = p

    en_by_num = {}
    for p in en_clauses:
        num = _extract_clause_number(p)
        if num:
            en_by_num[num] = p

    matched_cn = set()
    matched_en = set()

    for num in cn_by_num:
        if num in en_by_num:
            alignments.append(BilingualAlignment(
                index=len(alignments),
                cn_text=cn_by_num[num],
                en_text=en_by_num[num],
                confidence=0.9,
            ))
            matched_cn.add(num)
            matched_en.add(num)

    # 按顺序对齐剩余
    remaining_cn = [p for p in cn_clauses if _extract_clause_number(p) not in matched_cn]
    remaining_en = [p for p in en_clauses if _extract_clause_number(p) not in matched_en]

    min_len = min(len(remaining_cn), len(remaining_en))
    for i in range(min_len):
        alignments.append(BilingualAlignment(
            index=len(alignments),
            cn_text=remaining_cn[i],
            en_text=remaining_en[i],
            confidence=0.6,
        ))

    for i in range(min_len, len(remaining_cn)):
        alignments.append(BilingualAlignment(
            index=len(alignments),
            cn_text=remaining_cn[i],
            en_text="",
            confidence=0.0,
        ))

    for i in range(min_len, len(remaining_en)):
        alignments.append(BilingualAlignment(
            index=len(alignments),
            cn_text="",
            en_text=remaining_en[i],
            confidence=0.0,
        ))

    return alignments


def check_term_consistency(alignments: List[BilingualAlignment]) -> List[Dict]:
    """检查术语翻译一致性"""
    issues = []
    term_usage = {}

    for al in alignments:
        if not al.cn_text or not al.en_text:
            continue

        for cn_term, en_variants in CONTRACT_TERMS_MAP.items():
            if cn_term not in al.cn_text:
                continue

            found = False
            matched_variant = None
            for variant in en_variants:
                if variant.lower() in al.en_text.lower():
                    found = True
                    matched_variant = variant
                    break

            if not found:
                issues.append({
                    "type": "missing_translation",
                    "severity": "medium",
                    "clause_index": al.index,
                    "cn_term": cn_term,
                    "cn_context": al.cn_text[:100],
                    "en_context": al.en_text[:100],
                    "expected": en_variants[0],
                    "description": f"中文术语'{cn_term}'在英文段落中未找到对应翻译",
                })
            else:
                if cn_term not in term_usage:
                    term_usage[cn_term] = {}
                if matched_variant not in term_usage[cn_term]:
                    term_usage[cn_term][matched_variant] = []
                term_usage[cn_term][matched_variant].append(al.index)

    for cn_term, translations in term_usage.items():
        if len(translations) > 1:
            variants = list(translations.keys())
            issues.append({
                "type": "inconsistent_translation",
                "severity": "medium",
                "cn_term": cn_term,
                "variants": variants,
                "locations": {v: translations[v] for v in variants},
                "description": f"术语'{cn_term}'存在不一致翻译: {' / '.join(variants)}",
            })

    return issues


def check_clause_consistency(alignments: List[BilingualAlignment]) -> List[Dict]:
    """检查中英文条款内容一致性（金额/日期/义务）"""
    issues = []

    for al in alignments:
        if not al.cn_text or not al.en_text or al.confidence < 0.5:
            continue

        # 金额一致性
        cn_amounts = re.findall(r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:元|人民币|万元|美元|美金)', al.cn_text)
        en_amounts = re.findall(r'(?:USD|CNY|RMB|EUR)\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)', al.en_text)

        if cn_amounts and en_amounts:
            cn_nums = set(float(a.replace(',', '')) for a in cn_amounts)
            en_nums = set(float(a.replace(',', '')) for a in en_amounts)
            if cn_nums != en_nums:
                issues.append({
                    "type": "amount_mismatch",
                    "severity": "high",
                    "clause_index": al.index,
                    "cn_amounts": list(cn_nums),
                    "en_amounts": list(en_nums),
                    "cn_context": al.cn_text[:150],
                    "en_context": al.en_text[:150],
                    "description": f"金额不一致: 中文{cn_nums} vs 英文{en_nums}",
                })

        # 日期一致性
        cn_dates = re.findall(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', al.cn_text)
        en_dates = re.findall(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', al.en_text)

        if cn_dates and en_dates:
            cn_date_strs = set(f"{y}-{m.zfill(2)}-{d.zfill(2)}" for y, m, d in cn_dates)
            en_date_strs = set(f"{y}-{m.zfill(2)}-{d.zfill(2)}" for y, m, d in en_dates)
            if cn_date_strs != en_date_strs:
                issues.append({
                    "type": "date_mismatch",
                    "severity": "high",
                    "clause_index": al.index,
                    "cn_dates": list(cn_date_strs),
                    "en_dates": list(en_date_strs),
                    "description": f"日期不一致: 中文{cn_date_strs} vs 英文{en_date_strs}",
                })

    return issues


def check_language_priority(text: str) -> List[Dict]:
    """检查语言优先级条款"""
    issues = []

    cn_priority = re.search(
        r'(?:中英文|中文和英文|两种文字|双语|语言).*?(?:以.*?为准|优先|具有同等效力)',
        text
    )
    en_priority = re.search(
        r'(?:Chinese|English|bilingual|language).*?(?:prevail|priority|equally authentic)',
        text,
        re.IGNORECASE
    )

    if not cn_priority and not en_priority:
        issues.append({
            "type": "missing_language_priority",
            "severity": "high",
            "description": "双语合同未明确约定语言优先级条款",
            "suggestion": "本合同以中文和英文书就，两种文本具有同等效力。如两种文本存在歧义，以中文版本为准。",
        })

    if cn_priority and "同等效力" in cn_priority.group() and "歧义" not in cn_priority.group():
        issues.append({
            "type": "ambiguous_priority",
            "severity": "medium",
            "description": "约定'同等效力'但未约定歧义时的处理方式",
            "suggestion": "建议补充：如两种文本存在歧义，以[中文/英文]版本为准。",
        })

    return issues


def review_bilingual_contract(
    cn_text: str,
    en_text: str,
    contract_type: str = "other",
) -> Dict:
    """
    双语合同审查主入口

    Args:
        cn_text: 中文合同文本
        en_text: 英文合同文本
        contract_type: 合同类型

    Returns:
        审查结果字典
    """
    alignments = align_bilingual(cn_text, en_text)
    translation_issues = check_term_consistency(alignments)
    consistency_issues = check_clause_consistency(alignments)
    priority_issues = check_language_priority(cn_text)

    all_issues = consistency_issues + translation_issues + priority_issues

    high_count = sum(1 for i in all_issues if i.get("severity") == "high")
    medium_count = sum(1 for i in all_issues if i.get("severity") == "medium")
    low_count = sum(1 for i in all_issues if i.get("severity") == "low")

    aligned_count = sum(1 for a in alignments if a.confidence > 0)
    unaligned_cn = sum(1 for a in alignments if a.cn_text and not a.en_text)
    unaligned_en = sum(1 for a in alignments if a.en_text and not a.cn_text)

    return {
        "summary": {
            "total_paragraphs": len(alignments),
            "aligned_pairs": aligned_count,
            "unaligned_cn": unaligned_cn,
            "unaligned_en": unaligned_en,
            "total_issues": len(all_issues),
            "risk_distribution": {"high": high_count, "medium": medium_count, "low": low_count},
            "overall_risk": "high" if high_count > 0 else ("medium" if medium_count > 2 else "low"),
        },
        "alignments": [
            {
                "index": a.index,
                "cn_text": a.cn_text[:200],
                "en_text": a.en_text[:200],
                "confidence": a.confidence,
            }
            for a in alignments
        ],
        "consistency_issues": consistency_issues,
        "translation_issues": translation_issues,
        "priority_issues": priority_issues,
        "all_issues": all_issues,
    }
