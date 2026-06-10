"""
专项风控规则库
23条行业风控规则 (IR-001 ~ IR-023)
14种毒丸条款检测
四维加权风险评估模型
"""

import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# 四维加权风险评估模型
RISK_DIMENSIONS = {
    "severity": {"name": "严重度", "weight": 0.40},
    "probability": {"name": "可能性", "weight": 0.25},
    "financial_exposure": {"name": "财务敞口", "weight": 0.20},
    "responsibility_imbalance": {"name": "责任不对等", "weight": 0.15},
}

# 23条行业风控规则
INDUSTRY_RISK_RULES = [
    {"id": "IR-001", "name": "价格调整风险", "cat": "procurement",
     "desc": "缺乏价格调整机制", "sev": 0.7,
     "check": lambda t: ("价格" in t or "单价" in t) and ("调整" in t or "变更" in t) and not re.search(r"调[整价].*条件|涨幅.*[%％]|调价机制", t),
     "sug": "建议明确价格调整触发条件、调整幅度上限和调整周期"},
    {"id": "IR-002", "name": "材质证明缺失", "cat": "procurement",
     "desc": "未要求材质证明", "sev": 0.6,
     "check": lambda t: ("采购" in t or "买" in t) and ("材料" in t or "材质" in t) and "材质证明" not in t and "检验报告" not in t,
     "sug": "要求供应商提供材质证明、出厂检验报告"},
    {"id": "IR-003", "name": "异议期风险", "cat": "procurement,sales",
     "desc": "未约定质量异议期", "sev": 0.6,
     "check": lambda t: re.search(r"异议|验收|检验", t) and not re.search(r"异议期|验收期|检验期.*\d+.*天|日", t),
     "sug": "建议约定合理的质量异议期（通常7-15天）"},
    {"id": "IR-004", "name": "预付款风险", "cat": "sales",
     "desc": "预付款比例过高", "sev": 0.8,
     "check": lambda t: bool(re.search(r"预付.*([5-9]\d|100)[%％]", t)),
     "sug": "预付款超过50%时建议要求银行保函"},
    {"id": "IR-005", "name": "赔偿上限风险", "cat": "sales,outsourcing",
     "desc": "赔偿上限缺失", "sev": 0.7,
     "check": lambda t: re.search(r"赔偿|损失|损害", t) and not re.search(r"赔偿.*上限|限额|不超过|以.*为限", t),
     "sug": "建议约定赔偿上限（通常不超过合同总金额）"},
    {"id": "IR-006", "name": "模具费用风险", "cat": "sales,outsourcing",
     "desc": "模具费用归属不明", "sev": 0.5,
     "check": lambda t: "模具" in t and not re.search(r"模具.*费用|归属|产权|承担", t),
     "sug": "明确模具费用承担方、归属权"},
    {"id": "IR-007", "name": "二次外协风险", "cat": "outsourcing",
     "desc": "可能二次转包", "sev": 0.8,
     "check": lambda t: ("外协" in t or "加工" in t or "承揽" in t) and not re.search(r"不得|禁止.*转包|分包|二次外协", t),
     "sug": "明确禁止二次外协/转包，约定违约责任"},
    {"id": "IR-008", "name": "环保合规风险(外协)", "cat": "outsourcing",
     "desc": "外协环保责任不明", "sev": 0.6,
     "check": lambda t: ("外协" in t or "加工" in t) and "环保" in t and not re.search(r"环保.*责任|义务|费用", t),
     "sug": "明确外协环保责任承担方"},
    {"id": "IR-009", "name": "设备质保风险", "cat": "procurement",
     "desc": "设备质保期缺失", "sev": 0.7,
     "check": lambda t: "设备" in t and not re.search(r"质保.*\d+.*年|月", t),
     "sug": "建议约定设备质保期（通常12-24个月）"},
    {"id": "IR-010", "name": "交期违约金", "cat": "procurement",
     "desc": "交期违约条款缺失", "sev": 0.6,
     "check": lambda t: re.search(r"交[期货付]", t) and not re.search(r"违约|逾期|延期.*\d+.*[%％]|元|天", t),
     "sug": "建议约定交期违约金（每日0.1%-0.5%）"},
    {"id": "IR-011", "name": "不可抗力风险", "cat": "all",
     "desc": "不可抗力条款缺失", "sev": 0.6,
     "check": lambda t: "不可抗力" not in t and len(t) > 500,
     "sug": "建议增加不可抗力条款"},
    {"id": "IR-012", "name": "管辖约定风险", "cat": "all",
     "desc": "争议管辖约定不明", "sev": 0.5,
     "check": lambda t: not re.search(r"管辖|仲裁|法院|仲裁委", t) and len(t) > 500,
     "sug": "明确争议解决方式和管辖地"},
    {"id": "IR-013", "name": "保密风险(外协)", "cat": "outsourcing",
     "desc": "技术信息未约定保密", "sev": 0.7,
     "check": lambda t: ("外协" in t or "加工" in t) and re.search(r"图纸|工艺|技术|配方", t) and "保密" not in t,
     "sug": "增加保密条款，明确保密范围和期限"},
    {"id": "IR-014", "name": "知识产权风险", "cat": "outsourcing",
     "desc": "知识产权归属不明", "sev": 0.7,
     "check": lambda t: ("外协" in t or "加工" in t) and re.search(r"设计|研发|开发|改进", t) and not re.search(r"知识产权|专利|著作权|归属", t),
     "sug": "明确知识产权归属和使用权限"},
    {"id": "IR-015", "name": "环保合规风险", "cat": "sales",
     "desc": "环保要求缺失", "sev": 0.7,
     "check": lambda t: re.search(r"环保|RoHS|REACH|有害物质", t, re.I) and not re.search(r"符合|遵守.*环保", t),
     "sug": "明确产品需符合的环保法规"},
    {"id": "IR-016", "name": "招投标合规风险", "cat": "sales",
     "desc": "招投标文件不完整", "sev": 0.8,
     "check": lambda t: re.search(r"招投标|招标|投标|中标", t) and not re.search(r"中标通知书|招标文件|投标文件|评标", t),
     "sug": "确保招投标文件完整"},
    {"id": "IR-017", "name": "租金调整风险", "cat": "lease",
     "desc": "租金调整机制不明", "sev": 0.6,
     "check": lambda t: "租" in t and re.search(r"调[整涨]|递增", t) and not re.search(r"调整.*上限|幅度|不超过|每年", t),
     "sug": "明确租金调整周期和幅度上限"},
    {"id": "IR-018", "name": "转租限制风险", "cat": "lease",
     "desc": "转租限制不明", "sev": 0.5,
     "check": lambda t: "租" in t and "转租" not in t and "分租" not in t,
     "sug": "明确转租限制条件和审批流程"},
    {"id": "IR-019", "name": "电价挂钩风险", "cat": "lease",
     "desc": "电价挂钩机制不明", "sev": 0.6,
     "check": lambda t: re.search(r"供电|电费|电价", t) and not re.search(r"电价.*调整|挂钩|浮动|基准", t),
     "sug": "明确电价计算方式和调整周期"},
    {"id": "IR-020", "name": "线损分摊风险", "cat": "lease",
     "desc": "线损分摊方式不明", "sev": 0.5,
     "check": lambda t: re.search(r"供电|转供电", t) and re.search(r"线[损路]|损耗", t) and not re.search(r"线损.*分摊|承担|比例", t),
     "sug": "明确线损计算方式和分摊比例"},
    {"id": "IR-021", "name": "延迟违约金", "cat": "logistics",
     "desc": "物流延迟违约条款缺失", "sev": 0.6,
     "check": lambda t: re.search(r"运输|物流|配送", t) and not re.search(r"延迟|逾期|延期.*违约|赔偿|罚", t),
     "sug": "约定延迟交付违约金和免责条件"},
    {"id": "IR-022", "name": "承运资质风险", "cat": "logistics",
     "desc": "未审核承运资质", "sev": 0.5,
     "check": lambda t: re.search(r"运输|物流", t) and not re.search(r"资质|许可证|营运证|道路运输", t),
     "sug": "要求承运方提供道路运输许可证"},
    {"id": "IR-023", "name": "货损赔偿风险", "cat": "logistics",
     "desc": "货损赔偿标准不明", "sev": 0.7,
     "check": lambda t: re.search(r"运输|物流", t) and re.search(r"损[坏失]|灭失|丢失", t) and not re.search(r"赔偿.*标准|金额|比例|计算方式", t),
     "sug": "明确货损赔偿标准和理赔时效"},
]

# 14种毒丸条款检测
POISON_PILL_PATTERNS = [
    # 结构隐藏型 (5种)
    {"id": "PP-S1", "name": "自动续约陷阱", "type": "structural", "sev": 0.8,
     "pat": r"自动续约|自动续期|默认续[约期]|未.*通知.*终止.*续"},
    {"id": "PP-S2", "name": "无限连带责任", "type": "structural", "sev": 0.9,
     "pat": r"连带责任|无限责任|无上限.*赔偿"},
    {"id": "PP-S3", "name": "单方修改权", "type": "structural", "sev": 0.8,
     "pat": r"(?:甲方|一方).*(?:有权|可以|单[独方]).*(?:修改|变更|调整).*(?:合同|条款)"},
    {"id": "PP-S4", "name": "排他性绑定", "type": "structural", "sev": 0.7,
     "pat": r"独家|排他|唯一|不得.*其他.*(?:合作|交易|采购)"},
    {"id": "PP-S5", "name": "永久授权", "type": "structural", "sev": 0.8,
     "pat": r"永久|不可撤销|无期限.*(?:授权|许可|使用权)"},
    # 语言红旗型 (8种)
    {"id": "PP-L1", "name": "模糊表述过多", "type": "linguistic", "sev": 0.5,
     "pat": r"合理|适当|相应|相关|尽快|酌情|视情况|原则上"},
    {"id": "PP-L2", "name": "兜底条款过宽", "type": "linguistic", "sev": 0.6,
     "pat": r"包括但不限于|但不限于|及其他|以及其他|类似"},
    {"id": "PP-L3", "name": "绝对化表述", "type": "linguistic", "sev": 0.6,
     "pat": r"任何.*情况.*都|一律|无条件|绝对|完全|全部"},
    {"id": "PP-L4", "name": "歧义条款", "type": "linguistic", "sev": 0.5,
     "pat": r"或者.*或者|可以.*也可以|可.*亦可|任选"},
    {"id": "PP-L5", "name": "引用过时法规", "type": "linguistic", "sev": 0.7,
     "pat": r"《合同法》|《经济合同法》|《涉外经济合同法》|《技术合同法》"},
    {"id": "PP-L6", "name": "单方面免责", "type": "linguistic", "sev": 0.7,
     "pat": r"(?:甲方|我方).*(?:不承担|免除|无需).*责任"},
    {"id": "PP-L7", "name": "过度违约金", "type": "linguistic", "sev": 0.7,
     "pat": r"违约金.*(?:30|40|50|60|70|80|90|100)[%％]|每日.*违约金.*[1-9][%％]"},
    {"id": "PP-L8", "name": "无限担保", "type": "linguistic", "sev": 0.8,
     "pat": r"无条件担保|无限期担保|绝对保证|完全负责"},
    # 行为模式型 (1种)
    {"id": "PP-B1", "name": "关联交易未披露", "type": "behavioral", "sev": 0.7,
     "pat": r"(?:关联方|关联企业|关联公司).*(?:交易|采购|销售)"},
]

# 41类条款识别
CLAUSE_CATEGORIES = [
    {"id": "CL-01", "name": "合同主体条款", "pat": [r"甲方|乙方|丙方|买方|卖方"]},
    {"id": "CL-02", "name": "合同标的条款", "pat": [r"标的|产品|货物|商品|设备|材料"]},
    {"id": "CL-03", "name": "数量条款", "pat": [r"数量|总量|批量|件|台|套|吨|千克"]},
    {"id": "CL-04", "name": "质量条款", "pat": [r"质量|品质|规格|型号|标准|等级"]},
    {"id": "CL-05", "name": "价款条款", "pat": [r"价格|单价|总价|金额|价款|费用"]},
    {"id": "CL-06", "name": "支付条款", "pat": [r"付款|支付|账期|预付|分期|结算"]},
    {"id": "CL-07", "name": "交付条款", "pat": [r"交货|交付|发货|运输|物流|配送"]},
    {"id": "CL-08", "name": "验收条款", "pat": [r"验收|检验|检测|测试|确认"]},
    {"id": "CL-09", "name": "质保条款", "pat": [r"质保|保修|保质|维修|保养"]},
    {"id": "CL-10", "name": "违约责任条款", "pat": [r"违约|赔偿|罚款|罚金|滞纳金"]},
    {"id": "CL-11", "name": "争议解决条款", "pat": [r"争议|纠纷|仲裁|诉讼|管辖|调解"]},
    {"id": "CL-12", "name": "保密条款", "pat": [r"保密|机密|秘密|商业秘密|竞业"]},
    {"id": "CL-13", "name": "知识产权条款", "pat": [r"知识产权|专利|商标|著作权|版权"]},
    {"id": "CL-14", "name": "不可抗力条款", "pat": [r"不可抗力|自然灾害|战争|疫情|政策变化"]},
    {"id": "CL-15", "name": "合同解除条款", "pat": [r"解除|终止|撤销|取消|退约"]},
    {"id": "CL-16", "name": "合同期限条款", "pat": [r"期限|有效期|起始|截止|届满"]},
    {"id": "CL-17", "name": "通知送达条款", "pat": [r"通知|送达|公告|邮寄|电子邮件"]},
    {"id": "CL-18", "name": "转让限制条款", "pat": [r"转让|转包|分包|让与"]},
    {"id": "CL-19", "name": "保险条款", "pat": [r"保险|投保|保单|理赔"]},
    {"id": "CL-20", "name": "税务条款", "pat": [r"税|发票|增值税|税率"]},
]


def check_industry_risks(text: str, contract_category: str = "all") -> List[Dict]:
    """执行23条行业风控规则检查"""
    results = []
    for rule in INDUSTRY_RISK_RULES:
        try:
            if rule["cat"] == "all" or contract_category in rule["cat"]:
                if rule["check"](text):
                    results.append({
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "description": rule["desc"],
                        "severity": rule["sev"],
                        "suggestion": rule["sug"],
                        "category": rule["cat"],
                    })
        except Exception as e:
            logger.warning(f"Rule {rule['id']} check error: {e}")
    return results


def detect_poison_pills(text: str) -> List[Dict]:
    """检测14种毒丸条款"""
    results = []
    for pp in POISON_PILL_PATTERNS:
        try:
            if re.search(pp["pat"], text):
                match = re.search(pp["pat"], text)
                results.append({
                    "pattern_id": pp["id"],
                    "name": pp["name"],
                    "type": pp["type"],
                    "severity": pp["sev"],
                    "matched_text": match.group()[:100] if match else "",
                })
        except Exception as e:
            logger.warning(f"Poison pill {pp['id']} error: {e}")
    return results


def identify_clauses(text: str) -> List[Dict]:
    """识别41类条款"""
    found = []
    for cat in CLAUSE_CATEGORIES:
        for pat in cat["pat"]:
            if re.search(pat, text):
                found.append({"id": cat["id"], "name": cat["name"]})
                break
    return found


def calc_risk_score(severity: float, probability: float, financial: float, imbalance: float) -> float:
    """四维加权风险评分"""
    score = (
        severity * RISK_DIMENSIONS["severity"]["weight"] +
        probability * RISK_DIMENSIONS["probability"]["weight"] +
        financial * RISK_DIMENSIONS["financial_exposure"]["weight"] +
        imbalance * RISK_DIMENSIONS["responsibility_imbalance"]["weight"]
    )
    return round(score, 2)


def full_risk_analysis(text: str, contract_category: str = "all") -> Dict:
    """完整风控分析"""
    industry_risks = check_industry_risks(text, contract_category)
    poison_pills = detect_poison_pills(text)
    clauses = identify_clauses(text)

    # 计算综合风险分
    max_severity = max([r["severity"] for r in industry_risks] + [0])
    max_pp_severity = max([p["severity"] for p in poison_pills] + [0])
    combined_severity = max(max_severity, max_pp_severity)

    risk_score = calc_risk_score(
        severity=combined_severity,
        probability=min(len(industry_risks) * 0.15, 1.0),
        financial=min(len(poison_pills) * 0.2, 1.0),
        imbalance=min(len([p for p in poison_pills if p["type"] == "structural"]) * 0.25, 1.0),
    )

    return {
        "risk_score": risk_score,
        "risk_level": "高" if risk_score >= 0.7 else ("中" if risk_score >= 0.4 else "低"),
        "industry_risks": industry_risks,
        "industry_risks_count": len(industry_risks),
        "poison_pills": poison_pills,
        "poison_pills_count": len(poison_pills),
        "identified_clauses": clauses,
        "identified_clauses_count": len(clauses),
        "dimensions": RISK_DIMENSIONS,
    }
