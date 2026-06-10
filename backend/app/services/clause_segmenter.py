"""
合同条款分割引擎
将合同全文拆分为独立条款，逐条分析
支持多级条款（条/款/项）
"""

import re
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# 条款分割正则模式
CLAUSE_SPLIT_PATTERNS = [
    # 第X条 / 第X章
    r"(第[一二三四五六七八九十百千\d]+[条章节])",
    # 数字序号: 1. / 1、/ 1) / (1)
    r"(\d+[\.、\)）]\s*)",
    # 中文序号: （一）/ （二）
    r"([（\(][一二三四五六七八九十]+[）\)]\s*)",
]

# 条款标题识别
CLAUSE_TITLE_PATTERNS = [
    r"^第[一二三四五六七八九十百千\d]+[条章节]\s*[：:]\s*(.+)",
    r"^第[一二三四五六七八九十百千\d]+[条章节]\s+(.+)",
    r"^\d+[\.、]\s*(.+)",
]


def segment_clauses(text: str) -> List[Dict]:
    """
    将合同全文分割为独立条款
    返回: [{"index": 1, "title": "条款标题", "content": "条款内容", "level": 1}]
    """
    if not text:
        return []

    # 清理文本
    text = text.strip()

    # 尝试按"第X条"分割
    clauses = _split_by_chinese_numbered_articles(text)

    if len(clauses) < 3:
        # 如果条款太少，尝试按数字序号分割
        clauses = _split_by_number_prefix(text)

    if len(clauses) < 3:
        # 仍然太少，按段落分割
        clauses = _split_by_paragraph(text)

    # 为每个条款添加分析
    result = []
    for i, (title, content) in enumerate(clauses, 1):
        clause = {
            "index": i,
            "title": title.strip() if title else f"第{i}款",
            "content": content.strip(),
            "level": _detect_clause_level(title or content),
            "word_count": len(content.strip()),
            "has_risk_keywords": _has_risk_keywords(content),
        }
        result.append(clause)

    return result


def _split_by_chinese_numbered_articles(text: str) -> List[Tuple[str, str]]:
    """按第X条分割"""
    pattern = r"(第[一二三四五六七八九十百千\d]+[条章节])"
    parts = re.split(pattern, text)

    clauses = []
    current_title = ""
    current_content = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if re.match(pattern, part):
            # 保存上一条
            if current_content:
                clauses.append((current_title, current_content))
            current_title = part
            current_content = ""
        else:
            current_content += part

    # 保存最后一条
    if current_content:
        clauses.append((current_title, current_content))

    return clauses


def _split_by_number_prefix(text: str) -> List[Tuple[str, str]]:
    """按数字序号分割"""
    pattern = r"\n\s*(\d+[\.、\)）])\s*"
    parts = re.split(pattern, text)

    clauses = []
    current_title = ""
    current_content = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if re.match(r"\d+[\.、\)）]", part):
            if current_content:
                clauses.append((current_title, current_content))
            current_title = part
            current_content = ""
        else:
            current_content += " " + part

    if current_content:
        clauses.append((current_title, current_content))

    return clauses


def _split_by_paragraph(text: str) -> List[Tuple[str, str]]:
    """按段落分割"""
    paragraphs = re.split(r"\n\s*\n|\n", text)
    clauses = []
    for i, para in enumerate(paragraphs, 1):
        para = para.strip()
        if len(para) > 10:  # 过滤空行和极短行
            clauses.append((f"第{i}段", para))
    return clauses


def _detect_clause_level(text: str) -> int:
    """检测条款层级"""
    if re.match(r"第[一二三四五六七八九十百千\d]+[条章]", text):
        return 1
    elif re.match(r"第[一二三四五六七八九十百千\d]+[款]", text):
        return 2
    elif re.match(r"\d+[\.、]", text):
        return 2
    elif re.match(r"[（\(][一二三四五六七八九十]+[）\)]", text):
        return 3
    return 1


def _has_risk_keywords(text: str) -> bool:
    """检测是否包含风险关键词"""
    risk_keywords = [
        "违约", "赔偿", "罚款", "罚金", "滞纳金", "解除", "终止",
        "不可抗力", "免责", "担保", "连带责任", "保密", "竞业",
        "知识产权", "专利", "争议", "仲裁", "诉讼", "管辖",
        "自动续约", "排他", "独家", "永久", "不可撤销",
    ]
    return any(kw in text for kw in risk_keywords)


def analyze_clause_risks(clauses: List[Dict]) -> List[Dict]:
    """分析每个条款的风险"""
    risk_keywords = {
        "high": ["违约金", "赔偿", "连带责任", "无限责任", "自动续约", "不可撤销", "排他", "独家"],
        "medium": ["保证金", "预付款", "质保", "维修", "保密", "竞业", "知识产权"],
        "low": ["通知", "送达", "公告", "联系方式"],
    }

    for clause in clauses:
        content = clause["content"]
        clause["risk_items"] = []

        for level, keywords in risk_keywords.items():
            for kw in keywords:
                if kw in content:
                    clause["risk_items"].append({
                        "keyword": kw,
                        "level": level,
                    })

        # 计算条款风险分
        high_count = sum(1 for r in clause["risk_items"] if r["level"] == "high")
        med_count = sum(1 for r in clause["risk_items"] if r["level"] == "medium")
        clause["clause_risk_score"] = min(high_count * 30 + med_count * 15, 100)

    return clauses


def get_clause_summary(clauses: List[Dict]) -> Dict:
    """获取条款统计摘要"""
    total = len(clauses)
    risk_clauses = sum(1 for c in clauses if c.get("has_risk_keywords"))
    total_words = sum(c.get("word_count", 0) for c in clauses)

    risk_distribution = {"high": 0, "medium": 0, "low": 0}
    for c in clauses:
        for item in c.get("risk_items", []):
            risk_distribution[item["level"]] = risk_distribution.get(item["level"], 0) + 1

    return {
        "total_clauses": total,
        "risk_clauses": risk_clauses,
        "total_words": total_words,
        "risk_distribution": risk_distribution,
    }
