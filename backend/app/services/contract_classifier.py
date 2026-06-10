"""
合同分类引擎 - 自动区分6大合同品类、17项细分合同子类型
分类识别准确率目标 >= 98%
"""

import re
import logging
from typing import Tuple, List, Dict, Optional

logger = logging.getLogger(__name__)

# 6大品类、17项细分
CONTRACT_TAXONOMY = {
    "procurement": {
        "name": "采购类",
        "subtypes": {
            "procurement_material": "原材料采购",
            "procurement_equipment": "设备采购",
            "procurement_mro": "MRO/耗材采购",
        },
        "keywords": ["采购", "购买", "买方", "卖方", "供货", "供方", "需方", "订货", "物资", "材料", "设备采购"],
        "patterns": [r"采购.*合同", r"买卖.*合同", r"订货.*合同", r"供货.*协议"],
    },
    "sales": {
        "name": "销售类",
        "subtypes": {
            "sales_product": "产品销售",
            "sales_export": "出口销售",
            "sales_domestic": "内销",
        },
        "keywords": ["销售", "出卖", "售方", "买方", "报价", "交付", "发货", "客户"],
        "patterns": [r"销售.*合同", r"产品.*销售", r"出口.*合同"],
    },
    "outsourcing": {
        "name": "外协加工类",
        "subtypes": {
            "outsourcing_processing": "委托加工",
            "outsourcing_subcontract": "分包加工",
            "outsourcing_technical": "技术外协",
        },
        "keywords": ["外协", "加工", "委托加工", "承揽", "定作", "分包", "代工", "OEM", "ODM"],
        "patterns": [r"外协.*合同", r"加工.*合同", r"委托.*加工", r"承揽.*合同"],
    },
    "logistics": {
        "name": "物流运输类",
        "subtypes": {
            "logistics_freight": "货运",
            "logistics_warehouse": "仓储",
            "logistics_express": "快递",
        },
        "keywords": ["运输", "物流", "货运", "承运", "仓储", "快递", "配送", "发货", "托运"],
        "patterns": [r"运输.*合同", r"物流.*合同", r"货运.*协议", r"仓储.*合同"],
    },
    "lease": {
        "name": "租赁/转供电类",
        "subtypes": {
            "lease_property": "厂房租赁",
            "lease_equipment": "设备租赁",
            "lease_power": "转供电",
        },
        "keywords": ["租赁", "租金", "转租", "供电", "转供电", "电费", "厂房", "场地", "物业"],
        "patterns": [r"租赁.*合同", r"厂房.*租赁", r"转供电.*协议", r"供电.*合同"],
    },
    "other": {
        "name": "综合类",
        "subtypes": {
            "other_service": "服务合同",
            "other_technical": "技术合同",
            "other_consulting": "咨询合同",
        },
        "keywords": ["服务", "咨询", "技术", "培训", "维护", "保养", "设计"],
        "patterns": [r"服务.*合同", r"技术.*合同", r"咨询.*协议"],
    },
}


def classify_contract(
    title: str = "",
    description: str = "",
    key_terms: str = "",
    file_content: Optional[str] = None,
) -> Tuple[str, str, float]:
    """
    合同自动分类
    
    Returns:
        (category, subtype, confidence) - 品类key, 细分key, 置信度0-1
    """
    text = f"{title} {description} {key_terms}"
    if file_content:
        # 取前2000字符用于分类
        text += f" {file_content[:2000]}"
    text = text.lower()

    scores = {}
    detail_scores = {}

    for cat_key, cat_info in CONTRACT_TAXONOMY.items():
        score = 0
        matched_keywords = []

        # 关键词匹配
        for kw in cat_info["keywords"]:
            if kw in text:
                score += 10
                matched_keywords.append(kw)

        # 正则匹配（权重更高）
        for pattern in cat_info.get("patterns", []):
            if re.search(pattern, text, re.IGNORECASE):
                score += 20

        scores[cat_key] = score
        detail_scores[cat_key] = matched_keywords

    if not any(scores.values()):
        return "other", "other_service", 0.3

    # 取最高分
    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]

    # 计算置信度
    total_score = sum(scores.values())
    confidence = best_score / total_score if total_score > 0 else 0.3
    confidence = min(confidence, 0.99)

    # 细分分类
    subtype = _classify_subtype(best_cat, text)

    logger.info(f"合同分类: {best_cat}/{subtype}, 置信度={confidence:.2f}, 匹配词={detail_scores[best_cat]}")

    return best_cat, subtype, confidence


def _classify_subtype(category: str, text: str) -> str:
    """细分分类"""
    cat_info = CONTRACT_TAXONOMY.get(category, {})
    subtypes = cat_info.get("subtypes", {})

    if not subtypes:
        return "other"

    # 对于采购类，进一步细分
    if category == "procurement":
        if any(kw in text for kw in ["设备", "机器", "机床", "生产线"]):
            return "procurement_equipment"
        elif any(kw in text for kw in ["材料", "原料", "钢材", "铝材", "元器件"]):
            return "procurement_material"
        else:
            return "procurement_mro"

    elif category == "sales":
        if any(kw in text for kw in ["出口", "外贸", "海运", "FOB", "CIF"]):
            return "sales_export"
        else:
            return "sales_domestic"

    elif category == "outsourcing":
        if any(kw in text for kw in ["分包", "转包"]):
            return "outsourcing_subcontract"
        elif any(kw in text for kw in ["技术", "研发", "设计"]):
            return "outsourcing_technical"
        else:
            return "outsourcing_processing"

    elif category == "logistics":
        if any(kw in text for kw in ["仓储", "仓库", "库房"]):
            return "logistics_warehouse"
        elif any(kw in text for kw in ["快递", "配送", "同城"]):
            return "logistics_express"
        else:
            return "logistics_freight"

    elif category == "lease":
        if any(kw in text for kw in ["供电", "电费", "转供电"]):
            return "lease_power"
        elif any(kw in text for kw in ["设备", "机器"]):
            return "lease_equipment"
        else:
            return "lease_property"

    # 综合类
    first_subtype = list(subtypes.keys())[0] if subtypes else "other_service"
    return first_subtype


def get_all_categories() -> List[dict]:
    """获取所有合同分类"""
    result = []
    for cat_key, cat_info in CONTRACT_TAXONOMY.items():
        subtypes = []
        for sub_key, sub_name in cat_info["subtypes"].items():
            subtypes.append({"key": sub_key, "name": sub_name})
        result.append({
            "key": cat_key,
            "name": cat_info["name"],
            "subtypes": subtypes,
        })
    return result


def get_category_label(category: str, subtype: str = None) -> str:
    """获取分类中文标签"""
    cat_info = CONTRACT_TAXONOMY.get(category, {})
    label = cat_info.get("name", category)
    if subtype and subtype in cat_info.get("subtypes", {}):
        label += f" - {cat_info['subtypes'][subtype]}"
    return label
