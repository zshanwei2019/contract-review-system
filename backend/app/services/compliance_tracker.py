"""
合规追踪服务
审查状态跟踪、合规检查清单、整改建议
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 合规检查清单模板
COMPLIANCE_CHECKLISTS = {
    "procurement": [
        {"id": "CC-P01", "item": "供应商资质审查", "required": True},
        {"id": "CC-P02", "item": "价格合理性评估", "required": True},
        {"id": "CC-P03", "item": "质量标准约定", "required": True},
        {"id": "CC-P04", "item": "交付时间可行性", "required": True},
        {"id": "CC-P05", "item": "违约责任条款", "required": True},
        {"id": "CC-P06", "item": "付款条件合规", "required": True},
        {"id": "CC-P07", "item": "验收标准明确", "required": True},
        {"id": "CC-P08", "item": "质保期约定", "required": False},
    ],
    "sales": [
        {"id": "CC-S01", "item": "客户资质审查", "required": True},
        {"id": "CC-S02", "item": "产品规格确认", "required": True},
        {"id": "CC-S03", "item": "价格条款确认", "required": True},
        {"id": "CC-S04", "item": "交付方式约定", "required": True},
        {"id": "CC-S05", "item": "验收标准明确", "required": True},
        {"id": "CC-S06", "item": "售后服务约定", "required": True},
        {"id": "CC-S07", "item": "违约责任条款", "required": True},
        {"id": "CC-S08", "item": "付款保障措施", "required": True},
    ],
    "outsourcing": [
        {"id": "CC-O01", "item": "承揽方资质审查", "required": True},
        {"id": "CC-O02", "item": "技术要求明确", "required": True},
        {"id": "CC-O03", "item": "质量标准约定", "required": True},
        {"id": "CC-O04", "item": "禁止转包条款", "required": True},
        {"id": "CC-O05", "item": "保密条款", "required": True},
        {"id": "CC-O06", "item": "知识产权归属", "required": True},
        {"id": "CC-O07", "item": "验收标准明确", "required": True},
        {"id": "CC-O08", "item": "违约责任条款", "required": True},
    ],
    "nda": [
        {"id": "CC-N01", "item": "保密范围明确", "required": True},
        {"id": "CC-N02", "item": "保密期限约定", "required": True},
        {"id": "CC-N03", "item": "违约责任条款", "required": True},
        {"id": "CC-N04", "item": "信息返还/销毁条款", "required": True},
        {"id": "CC-N05", "item": "竞业限制合理性", "required": False},
    ],
    "service": [
        {"id": "CC-SV01", "item": "服务范围明确", "required": True},
        {"id": "CC-SV02", "item": "服务标准约定", "required": True},
        {"id": "CC-SV03", "item": "服务期限约定", "required": True},
        {"id": "CC-SV04", "item": "费用及支付方式", "required": True},
        {"id": "CC-SV05", "item": "违约责任条款", "required": True},
    ],
    "lease": [
        {"id": "CC-L01", "item": "租赁物描述", "required": True},
        {"id": "CC-L02", "item": "租赁期限约定", "required": True},
        {"id": "CC-L03", "item": "租金及支付方式", "required": True},
        {"id": "CC-L04", "item": "维修责任约定", "required": True},
        {"id": "CC-L05", "item": "转租限制条款", "required": True},
        {"id": "CC-L06", "item": "违约责任条款", "required": True},
    ],
}


def get_checklist(contract_type: str) -> List[Dict]:
    """获取合同类型对应的合规检查清单"""
    return COMPLIANCE_CHECKLISTS.get(contract_type, COMPLIANCE_CHECKLISTS.get("other", []))


def evaluate_compliance(contract_type: str, review_findings: List[Dict]) -> Dict:
    """评估合同合规性"""
    checklist = get_checklist(contract_type)

    # 根据审查发现匹配检查清单
    results = []
    for item in checklist:
        matched = False
        related_finding = None

        for finding in review_findings:
            # 简单关键词匹配
            if _is_related(item["item"], finding.get("title", "") + finding.get("description", "")):
                matched = True
                related_finding = finding
                break

        status = "pass" if matched else ("fail" if item["required"] else "skip")
        results.append({
            "check_id": item["id"],
            "check_item": item["item"],
            "required": item["required"],
            "status": status,
            "related_finding": related_finding,
        })

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skip")

    compliance_rate = round(passed / total * 100, 1) if total > 0 else 0

    return {
        "contract_type": contract_type,
        "total_checks": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "compliance_rate": compliance_rate,
        "compliance_level": "高" if compliance_rate >= 80 else ("中" if compliance_rate >= 60 else "低"),
        "checklist_results": results,
    }


def _is_related(check_item: str, text: str) -> bool:
    """检查清单项与审查发现是否相关"""
    keywords = {
        "供应商资质": ["供应商", "资质", "营业执照"],
        "客户资质": ["客户", "资质", "营业执照"],
        "承揽方资质": ["承揽", "资质", "营业执照"],
        "价格": ["价格", "金额", "费用"],
        "质量": ["质量", "标准", "规格"],
        "交付": ["交付", "交货", "发货"],
        "验收": ["验收", "检验", "确认"],
        "违约": ["违约", "赔偿", "罚款"],
        "付款": ["付款", "支付", "账期"],
        "保密": ["保密", "机密", "秘密"],
        "知识产权": ["知识产权", "专利", "著作权"],
        "质保": ["质保", "保修", "维修"],
        "服务": ["服务", "售后", "支持"],
        "租赁": ["租赁", "租金", "租期"],
        "转租": ["转租", "分租"],
    }

    for key, kws in keywords.items():
        if key in check_item:
            return any(kw in text for kw in kws)

    return False


def generate_rectification_plan(compliance_result: Dict) -> List[Dict]:
    """生成整改计划"""
    plan = []
    for item in compliance_result.get("checklist_results", []):
        if item["status"] == "fail":
            plan.append({
                "check_item": item["check_item"],
                "priority": "高" if item["required"] else "中",
                "action": f"请补充或完善「{item['check_item']}」相关内容",
                "deadline_days": 3 if item["required"] else 7,
            })

    return plan
