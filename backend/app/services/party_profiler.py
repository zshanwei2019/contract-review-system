"""
相对方画像分析 (Counterparty Profiling)
- 基于历史合同数据分析相对方特征
- 风险倾向、谈判行为模式、条款偏好
- 生成相对方风险画像报告
"""
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from collections import Counter
from enum import Enum

logger = logging.getLogger(__name__)


class PartyRiskTier(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    UNKNOWN = "unknown"


class NegotiationStyle(str, Enum):
    COOPERATIVE = "cooperative"
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    BALANCED = "balanced"
    UNPREDICTABLE = "unpredictable"


@dataclass
class RiskPattern:
    pattern_type: str
    frequency: int = 0
    severity_avg: float = 0.0
    trend: str = "stable"
    examples: List[str] = field(default_factory=list)


@dataclass
class ClausePreference:
    clause_type: str
    tendency: str = "neutral"
    frequency: int = 0
    typical_wording: str = ""


@dataclass
class PartyProfile:
    party_name: str
    total_contracts: int = 0
    total_review_tasks: int = 0
    risk_tier: PartyRiskTier = PartyRiskTier.UNKNOWN
    overall_risk_score: float = 0.0
    negotiation_style: NegotiationStyle = NegotiationStyle.BALANCED
    avg_risk_score: float = 0.0
    avg_risk_count: float = 0.0
    high_risk_ratio: float = 0.0
    risk_patterns: List[RiskPattern] = field(default_factory=list)
    clause_preferences: List[ClausePreference] = field(default_factory=list)
    common_issues: List[str] = field(default_factory=list)
    risk_trend: str = "stable"
    cooperation_trend: str = "stable"
    recommendations: List[str] = field(default_factory=list)
    watch_points: List[str] = field(default_factory=list)


class PartyProfiler:
    """相对方画像分析器"""

    RISK_CATEGORIES = {
        "违约金": ["违约金", "逾期", "罚款", "赔偿"],
        "自动续约": ["自动续约", "自动延期", "自动展期"],
        "连带责任": ["连带", "无限责任", "担保"],
        "付款条款": ["付款", "支付", "结算", "价款"],
        "验收条款": ["验收", "检验", "检测", "标准"],
        "保密条款": ["保密", "竞业", "限制"],
        "知识产权": ["知识产权", "专利", "商标", "著作权"],
        "管辖条款": ["管辖", "仲裁", "诉讼", "争议解决"],
        "质保条款": ["质保", "保修", "售后"],
        "交付条款": ["交付", "交货", "运输"],
    }

    def analyze(self, party_name: str,
                historical_contracts: List[Dict],
                historical_reviews: Optional[List[Dict]] = None) -> PartyProfile:
        if not historical_contracts and not historical_reviews:
            return PartyProfile(party_name=party_name)

        profile = PartyProfile(party_name=party_name)
        profile.total_contracts = len(historical_contracts)
        profile.total_review_tasks = len(historical_reviews) if historical_reviews else 0

        all_findings = []
        risk_scores = []
        for review in (historical_reviews or []):
            findings = review.get("findings", [])
            all_findings.extend(findings)
            score = review.get("risk_score", review.get("combined_risk_score", 0))
            if score:
                risk_scores.append(float(score))

        if risk_scores:
            profile.avg_risk_score = sum(risk_scores) / len(risk_scores)
            profile.overall_risk_score = profile.avg_risk_score

        if all_findings and historical_contracts:
            profile.avg_risk_count = len(all_findings) / max(len(historical_contracts), 1)

        high_risks = [f for f in all_findings
                      if f.get("risk_level") == "high" or f.get("risk_score", 0) >= 70]
        profile.high_risk_ratio = len(high_risks) / max(len(all_findings), 1)

        profile.risk_tier = self._classify_risk_tier(profile)
        profile.negotiation_style = self._classify_negotiation_style(all_findings, profile)
        profile.risk_patterns = self._extract_risk_patterns(all_findings)
        profile.clause_preferences = self._extract_clause_preferences(all_findings)
        profile.common_issues = self._extract_common_issues(all_findings)
        profile.risk_trend = self._analyze_risk_trend(historical_reviews or [])
        profile.cooperation_trend = self._analyze_cooperation_trend(historical_contracts)
        profile.recommendations = self._generate_recommendations(profile)
        profile.watch_points = self._generate_watch_points(profile)

        return profile

    def _classify_risk_tier(self, p: PartyProfile) -> PartyRiskTier:
        if p.total_contracts < 2:
            return PartyRiskTier.UNKNOWN
        if p.avg_risk_score >= 70 or p.high_risk_ratio >= 0.4:
            return PartyRiskTier.HIGH
        elif p.avg_risk_score >= 50 or p.high_risk_ratio >= 0.25:
            return PartyRiskTier.ELEVATED
        elif p.avg_risk_score >= 30 or p.avg_risk_count >= 3:
            return PartyRiskTier.MODERATE
        return PartyRiskTier.LOW

    def _classify_negotiation_style(self, all_findings: List[Dict],
                                     profile: PartyProfile) -> NegotiationStyle:
        if not all_findings:
            return NegotiationStyle.BALANCED

        aggressive_kw = ["自动续约", "违约金", "连带责任", "单方", "无限"]
        defensive_kw = ["免责", "不可抗力", "责任限制", "质保期短"]
        cooperative_kw = ["协商", "友好", "合理", "双方"]

        agg = defn = coop = 0
        for f in all_findings:
            text = f.get("title", "") + f.get("description", "")
            if any(kw in text for kw in aggressive_kw):
                agg += 1
            elif any(kw in text for kw in defensive_kw):
                defn += 1
            elif any(kw in text for kw in cooperative_kw):
                coop += 1

        total = len(all_findings)
        if total == 0:
            return NegotiationStyle.BALANCED

        if agg / total > 0.4:
            return NegotiationStyle.AGGRESSIVE
        elif defn / total > 0.4:
            return NegotiationStyle.DEFENSIVE
        elif profile.avg_risk_score < 30:
            return NegotiationStyle.COOPERATIVE
        elif profile.high_risk_ratio > 0.3:
            return NegotiationStyle.UNPREDICTABLE
        return NegotiationStyle.BALANCED

    def _extract_risk_patterns(self, all_findings: List[Dict]) -> List[RiskPattern]:
        patterns = []
        for category, keywords in self.RISK_CATEGORIES.items():
            matches = [f for f in all_findings
                       if any(kw in f.get("title", "") + f.get("description", "") for kw in keywords)]
            if matches:
                sev_sum = sum(f.get("risk_score", f.get("combined_risk_score", 50)) for f in matches)
                patterns.append(RiskPattern(
                    pattern_type=category,
                    frequency=len(matches),
                    severity_avg=round(sev_sum / len(matches), 1),
                    examples=[m.get("title", "") for m in matches[:3]],
                ))
        patterns.sort(key=lambda x: x.frequency, reverse=True)
        return patterns[:8]

    def _extract_clause_preferences(self, all_findings: List[Dict]) -> List[ClausePreference]:
        prefs = []
        for category, keywords in self.RISK_CATEGORIES.items():
            matches = [f for f in all_findings
                       if any(kw in f.get("title", "") + f.get("description", "") for kw in keywords)]
            if matches:
                high_c = sum(1 for m in matches
                            if m.get("risk_level") == "high" or m.get("risk_score", 0) >= 70)
                ratio = high_c / len(matches)
                tendency = "unfavorable" if ratio > 0.5 else "neutral" if ratio > 0.2 else "favorable"
                prefs.append(ClausePreference(
                    clause_type=category,
                    tendency=tendency,
                    frequency=len(matches),
                    typical_wording=matches[0].get("description", "")[:100],
                ))
        prefs.sort(key=lambda x: x.frequency, reverse=True)
        return prefs[:8]

    def _extract_common_issues(self, all_findings: List[Dict]) -> List[str]:
        tc = Counter(f.get("title", "") for f in all_findings if f.get("title"))
        return [t for t, c in tc.most_common(10) if c >= 2]

    def _analyze_risk_trend(self, reviews: List[Dict]) -> str:
        if len(reviews) < 2:
            return "stable"
        sorted_r = sorted(reviews, key=lambda r: r.get("date", r.get("created_at", "")))
        scores = [float(r.get("risk_score", r.get("combined_risk_score", 0))) for r in sorted_r]
        if len(scores) < 2:
            return "stable"
        mid = len(scores) // 2
        a1 = sum(scores[:mid]) / mid
        a2 = sum(scores[mid:]) / (len(scores) - mid)
        diff = a2 - a1
        return "increasing" if diff > 10 else "decreasing" if diff < -10 else "stable"

    def _analyze_cooperation_trend(self, contracts: List[Dict]) -> str:
        if len(contracts) < 2:
            return "stable"
        sorted_c = sorted(contracts, key=lambda c: c.get("date", c.get("created_at", "")))
        dates = [c.get("date", c.get("created_at", "")) for c in sorted_c]
        recent = sum(1 for d in dates if d and ("2026" in str(d) or "2025" in str(d)))
        older = len(dates) - recent
        if recent > older * 2:
            return "increasing"
        elif recent < older / 2:
            return "decreasing"
        return "stable"

    def _generate_recommendations(self, p: PartyProfile) -> List[str]:
        recs = []
        if p.risk_tier in (PartyRiskTier.HIGH, PartyRiskTier.ELEVATED):
            recs.extend([
                "建议在签约前进行更详细的尽职调查",
                "重点审查违约金、自动续约、连带责任条款",
                "考虑增加合同终止权和退出机制",
            ])
        if p.negotiation_style == NegotiationStyle.AGGRESSIVE:
            recs.extend([
                "对方谈判风格偏进攻型，建议准备充分的谈判筹码",
                "在关键条款上坚持底线，避免被对方主导谈判节奏",
            ])
        if p.negotiation_style == NegotiationStyle.DEFENSIVE:
            recs.append("对方倾向于设置保护性条款，注意验收标准和质保条款")
        if p.risk_trend == "increasing":
            recs.append("⚠️ 风险呈上升趋势，建议关注近期合同变化")
        for pat in p.risk_patterns[:3]:
            if pat.frequency >= 2:
                recs.append(f"重点关注「{pat.pattern_type}」条款（历史出现{pat.frequency}次）")
        if not recs:
            recs.append("该相对方历史表现良好，按常规流程审查即可")
        return recs[:6]

    def _generate_watch_points(self, p: PartyProfile) -> List[str]:
        points = []
        for pat in p.risk_patterns:
            if pat.severity_avg >= 70:
                points.append(f"🔴 {pat.pattern_type}: 平均严重度{pat.severity_avg}分，需重点防范")
            elif pat.severity_avg >= 50:
                points.append(f"🟡 {pat.pattern_type}: 平均严重度{pat.severity_avg}分，需关注")
        if p.high_risk_ratio >= 0.3:
            points.append(f"⚠️ 高风险条款占比{p.high_risk_ratio:.0%}，高于正常水平")
        if p.avg_risk_count >= 5:
            points.append(f"⚠️ 平均每份合同{p.avg_risk_count:.0f}个风险项，条款质量偏低")
        return points[:6]

    def to_dict(self, p: PartyProfile) -> Dict:
        return {
            "party_name": p.party_name,
            "total_contracts": p.total_contracts,
            "total_review_tasks": p.total_review_tasks,
            "risk_tier": p.risk_tier.value,
            "overall_risk_score": round(p.overall_risk_score, 1),
            "negotiation_style": p.negotiation_style.value,
            "avg_risk_score": round(p.avg_risk_score, 1),
            "avg_risk_count": round(p.avg_risk_count, 1),
            "high_risk_ratio": round(p.high_risk_ratio, 2),
            "risk_trend": p.risk_trend,
            "cooperation_trend": p.cooperation_trend,
            "risk_patterns": [
                {"pattern_type": x.pattern_type, "frequency": x.frequency,
                 "severity_avg": x.severity_avg, "trend": x.trend, "examples": x.examples}
                for x in p.risk_patterns
            ],
            "clause_preferences": [
                {"clause_type": x.clause_type, "tendency": x.tendency,
                 "frequency": x.frequency, "typical_wording": x.typical_wording}
                for x in p.clause_preferences
            ],
            "common_issues": p.common_issues,
            "recommendations": p.recommendations,
            "watch_points": p.watch_points,
        }


def analyze_party(party_name: str,
                  historical_contracts: List[Dict],
                  historical_reviews: Optional[List[Dict]] = None) -> Dict:
    profiler = PartyProfiler()
    profile = profiler.analyze(party_name, historical_contracts, historical_reviews)
    return profiler.to_dict(profile)
