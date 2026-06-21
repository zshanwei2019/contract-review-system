"""
外部数据集成服务
- 企业工商信息查询 (企查查/天眼查风格)
- 司法风险查询 (裁判文书/开庭公告)
- 统一风险评估: 内部审查 + 外部数据
"""
import logging
import hashlib
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class CompanyInfo:
    """企业工商信息"""
    company_name: str
    credit_code: str = ""
    legal_person: str = ""
    registered_capital: str = ""
    established_date: str = ""
    status: str = "正常"
    business_scope: str = ""
    address: str = ""

    # 风险指标
    abnormal_count: int = 0       # 经营异常
    penalty_count: int = 0        # 行政处罚
    equity_frozen: bool = False   # 股权冻结
    bankruptcy: bool = False      # 破产清算

    risk_level: RiskLevel = RiskLevel.LOW
    risk_summary: str = ""


@dataclass
class LitigationRecord:
    """司法风险记录"""
    case_id: str = ""
    case_type: str = ""           # 民事/刑事/行政/执行
    case_title: str = ""
    role: str = ""                # 被告/原告/被执行人
    court: str = ""
    filing_date: str = ""
    amount: str = ""              # 涉案金额
    outcome: str = ""             # 判决结果
    risk_level: RiskLevel = RiskLevel.LOW


@dataclass
class ExternalRiskReport:
    """外部风险报告"""
    company_name: str
    company_info: Optional[CompanyInfo] = None
    litigation_records: List[LitigationRecord] = field(default_factory=list)
    total_litigation: int = 0
    as_defendant_count: int = 0
    execution_count: int = 0      # 被执行人次数
    overall_risk: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)


class ExternalDataSource(ABC):
    """外部数据源抽象基类"""

    @abstractmethod
    def query_company(self, company_name: str, credit_code: str = "") -> Optional[CompanyInfo]:
        ...

    @abstractmethod
    def query_litigation(self, company_name: str, limit: int = 20) -> List[LitigationRecord]:
        ...


class MockDataSource(ExternalDataSource):
    """
    模拟数据源 (开发/演示用)
    实际部署时替换为企查查/天眼查 API
    """

    # 模拟企业数据库
    _MOCK_COMPANIES = {
        "锋利刀具厂": {
            "credit_code": "91320500MA1XXXXXX1",
            "legal_person": "张锋",
            "registered_capital": "500万元",
            "established_date": "2010-03-15",
            "status": "正常",
            "business_scope": "刀具制造、销售；金属材料加工",
            "abnormal_count": 0,
            "penalty_count": 1,
            "equity_frozen": False,
            "bankruptcy": False,
        },
        "诚信机械有限公司": {
            "credit_code": "91320500MA1XXXXXX2",
            "legal_person": "李诚",
            "registered_capital": "2000万元",
            "established_date": "2005-08-20",
            "status": "正常",
            "business_scope": "机械设备制造、销售",
            "abnormal_count": 0,
            "penalty_count": 0,
            "equity_frozen": False,
            "bankruptcy": False,
        },
        "鑫达商贸": {
            "credit_code": "91320500MA1XXXXXX3",
            "legal_person": "王鑫",
            "registered_capital": "100万元",
            "established_date": "2018-01-10",
            "status": "正常",
            "business_scope": "商品贸易、进出口",
            "abnormal_count": 2,
            "penalty_count": 3,
            "equity_frozen": True,
            "bankruptcy": False,
        },
    }

    # 模拟司法数据
    _MOCK_LITIGATION = {
        "锋利刀具厂": [
            {"case_type": "民事", "case_title": "买卖合同纠纷", "role": "被告",
             "court": "苏州市中级人民法院", "filing_date": "2025-08-15",
             "amount": "50万元", "outcome": "调解结案"},
            {"case_type": "民事", "case_title": "产品质量纠纷", "role": "被告",
             "court": "苏州市工业园区法院", "filing_date": "2025-11-20",
             "amount": "30万元", "outcome": "判决赔偿"},
            {"case_type": "执行", "case_title": "合同纠纷执行", "role": "被执行人",
             "court": "苏州市工业园区法院", "filing_date": "2026-01-10",
             "amount": "30万元", "outcome": "执行中"},
        ],
        "鑫达商贸": [
            {"case_type": "民事", "case_title": "借款合同纠纷", "role": "被告",
             "court": "上海市浦东新区法院", "filing_date": "2025-06-10",
             "amount": "200万元", "outcome": "判决还款"},
            {"case_type": "执行", "case_title": "借款纠纷执行", "role": "被执行人",
             "court": "上海市浦东新区法院", "filing_date": "2025-09-15",
             "amount": "200万元", "outcome": "执行中"},
            {"case_type": "民事", "case_title": "劳动争议", "role": "被告",
             "court": "上海市浦东新区法院", "filing_date": "2025-12-01",
             "amount": "10万元", "outcome": "调解结案"},
            {"case_type": "行政", "case_title": "税务处罚", "role": "被处罚人",
             "court": "上海市税务局", "filing_date": "2026-02-20",
             "amount": "15万元", "outcome": "已缴纳"},
        ],
    }

    def query_company(self, company_name: str, credit_code: str = "") -> Optional[CompanyInfo]:
        # 模糊匹配
        for name, data in self._MOCK_COMPANIES.items():
            if company_name in name or name in company_name:
                info = CompanyInfo(
                    company_name=name,
                    credit_code=data["credit_code"],
                    legal_person=data["legal_person"],
                    registered_capital=data["registered_capital"],
                    established_date=data["established_date"],
                    status=data["status"],
                    business_scope=data["business_scope"],
                    abnormal_count=data["abnormal_count"],
                    penalty_count=data["penalty_count"],
                    equity_frozen=data["equity_frozen"],
                    bankruptcy=data["bankruptcy"],
                )
                info.risk_level, info.risk_summary = self._assess_company_risk(info)
                return info

        # 未找到 → 返回基础信息
        info = CompanyInfo(
            company_name=company_name,
            status="未查询到",
            risk_level=RiskLevel.MEDIUM,
            risk_summary="未查询到该企业工商信息，建议核实",
        )
        return info

    def query_litigation(self, company_name: str, limit: int = 20) -> List[LitigationRecord]:
        records = []
        for name, cases in self._MOCK_LITIGATION.items():
            if company_name in name or name in company_name:
                for case in cases[:limit]:
                    risk = RiskLevel.LOW
                    if case["role"] == "被执行人" or case["case_type"] == "执行":
                        risk = RiskLevel.HIGH
                    elif case["role"] == "被告" and case.get("outcome", "") == "判决赔偿":
                        risk = RiskLevel.MEDIUM

                    records.append(LitigationRecord(
                        case_id=hashlib.md5(case["case_title"].encode()).hexdigest()[:8],
                        case_type=case["case_type"],
                        case_title=case["case_title"],
                        role=case["role"],
                        court=case["court"],
                        filing_date=case["filing_date"],
                        amount=case["amount"],
                        outcome=case["outcome"],
                        risk_level=risk,
                    ))
                break
        return records

    def _assess_company_risk(self, info: CompanyInfo) -> Tuple[RiskLevel, str]:
        risk_score = 0
        reasons = []

        if info.status != "正常":
            risk_score += 30
            reasons.append(f"企业状态: {info.status}")

        if info.abnormal_count > 0:
            risk_score += info.abnormal_count * 15
            reasons.append(f"经营异常: {info.abnormal_count}次")

        if info.penalty_count > 0:
            risk_score += info.penalty_count * 10
            reasons.append(f"行政处罚: {info.penalty_count}次")

        if info.equity_frozen:
            risk_score += 25
            reasons.append("股权冻结")

        if info.bankruptcy:
            risk_score += 50
            reasons.append("破产清算")

        if risk_score >= 50:
            return RiskLevel.HIGH, "；".join(reasons)
        elif risk_score >= 25:
            return RiskLevel.MEDIUM, "；".join(reasons)
        else:
            return RiskLevel.LOW, "工商信息正常"


class ExternalRiskAssessor:
    """外部风险评估器 — 整合内部审查 + 外部数据"""

    def __init__(self, data_source: Optional[ExternalDataSource] = None):
        self.data_source = data_source or MockDataSource()

    def assess(self, company_name: str,
               internal_risk_score: float = 0.0,
               internal_findings: Optional[List[Dict]] = None,
               credit_code: str = "") -> ExternalRiskReport:
        """
        综合评估: 内部审查 + 外部数据
        """
        report = ExternalRiskReport(company_name=company_name)

        # 1. 企业工商信息
        report.company_info = self.data_source.query_company(company_name, credit_code)

        # 2. 司法风险
        report.litigation_records = self.data_source.query_litigation(company_name)
        report.total_litigation = len(report.litigation_records)
        report.as_defendant_count = sum(1 for r in report.litigation_records if r.role == "被告")
        report.execution_count = sum(1 for r in report.litigation_records if r.role == "被执行人")

        # 3. 综合评分
        external_score = self._calc_external_score(report)
        combined_score = self._combine_scores(internal_risk_score, external_score)
        report.risk_score = round(combined_score, 1)

        # 4. 风险等级
        report.overall_risk = self._classify_overall_risk(combined_score)

        # 5. 摘要
        report.summary = self._generate_summary(report, internal_risk_score, external_score)

        # 6. 建议
        report.recommendations = self._generate_recommendations(report)

        return report

    def _calc_external_score(self, report: ExternalRiskReport) -> float:
        score = 0.0

        # 工商风险
        if report.company_info:
            ci = report.company_info
            if ci.status != "正常":
                score += 30
            score += ci.abnormal_count * 15
            score += ci.penalty_count * 10
            if ci.equity_frozen:
                score += 25
            if ci.bankruptcy:
                score += 50

        # 司法风险
        score += report.execution_count * 20
        score += report.as_defendant_count * 8
        score += report.total_litigation * 3

        return min(100, score)

    def _combine_scores(self, internal: float, external: float) -> float:
        """内部60% + 外部40%"""
        return internal * 0.6 + external * 0.4

    def _classify_overall_risk(self, score: float) -> RiskLevel:
        if score >= 70:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _generate_summary(self, report: ExternalRiskReport,
                           internal_score: float, external_score: float) -> str:
        parts = []

        # 内部审查
        if internal_score >= 70:
            parts.append(f"内部审查风险较高 ({internal_score:.0f}分)")
        elif internal_score >= 40:
            parts.append(f"内部审查存在一定风险 ({internal_score:.0f}分)")
        else:
            parts.append(f"内部审查风险较低 ({internal_score:.0f}分)")

        # 外部数据
        if external_score >= 50:
            parts.append(f"外部数据风险较高 ({external_score:.0f}分)")
        elif external_score >= 25:
            parts.append(f"外部数据存在风险信号 ({external_score:.0f}分)")
        else:
            parts.append(f"外部数据风险较低 ({external_score:.0f}分)")

        # 司法
        if report.execution_count > 0:
            parts.append(f"存在{report.execution_count}条被执行记录")
        if report.total_litigation > 0:
            parts.append(f"涉及{report.total_litigation}起诉讼")

        return "；".join(parts)

    def _generate_recommendations(self, report: ExternalRiskReport) -> List[str]:
        recs = []

        if report.overall_risk == RiskLevel.HIGH:
            recs.append("🔴 综合风险较高，建议审慎评估是否继续合作")
            recs.append("建议要求对方提供担保或增加违约条款")

        if report.execution_count > 0:
            recs.append(f"⚠️ 对方有{report.execution_count}条被执行记录，关注履约能力")

        if report.company_info:
            ci = report.company_info
            if ci.abnormal_count > 0:
                recs.append(f"对方存在{ci.abnormal_count}次经营异常记录")
            if ci.equity_frozen:
                recs.append("⚠️ 对方存在股权冻结，关注经营稳定性")
            if ci.penalty_count > 0:
                recs.append(f"对方有{ci.penalty_count}次行政处罚记录")

        if report.as_defendant_count >= 3:
            recs.append("对方作为被告的诉讼较多，合同履行风险较高")

        if not recs:
            recs.append("外部数据未发现明显风险信号")

        return recs[:6]

    def to_dict(self, report: ExternalRiskReport) -> Dict:
        return {
            "company_name": report.company_name,
            "overall_risk": report.overall_risk.value,
            "risk_score": report.risk_score,
            "summary": report.summary,
            "recommendations": report.recommendations,
            "company_info": {
                "company_name": report.company_info.company_name,
                "credit_code": report.company_info.credit_code,
                "legal_person": report.company_info.legal_person,
                "registered_capital": report.company_info.registered_capital,
                "established_date": report.company_info.established_date,
                "status": report.company_info.status,
                "business_scope": report.company_info.business_scope,
                "abnormal_count": report.company_info.abnormal_count,
                "penalty_count": report.company_info.penalty_count,
                "equity_frozen": report.company_info.equity_frozen,
                "bankruptcy": report.company_info.bankruptcy,
                "risk_level": report.company_info.risk_level.value,
                "risk_summary": report.company_info.risk_summary,
            } if report.company_info else None,
            "litigation": {
                "total": report.total_litigation,
                "as_defendant": report.as_defendant_count,
                "execution": report.execution_count,
                "records": [
                    {
                        "case_id": r.case_id,
                        "case_type": r.case_type,
                        "case_title": r.case_title,
                        "role": r.role,
                        "court": r.court,
                        "filing_date": r.filing_date,
                        "amount": r.amount,
                        "outcome": r.outcome,
                        "risk_level": r.risk_level.value,
                    }
                    for r in report.litigation_records
                ],
            },
        }


def assess_external_risk(company_name: str,
                         internal_risk_score: float = 0.0,
                         internal_findings: Optional[List[Dict]] = None,
                         credit_code: str = "") -> Dict:
    """便捷函数"""
    assessor = ExternalRiskAssessor()
    report = assessor.assess(company_name, internal_risk_score, internal_findings, credit_code)
    return assessor.to_dict(report)
