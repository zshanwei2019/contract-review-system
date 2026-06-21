"""
谈判策略引擎 (Playbook)
- 基于审查结果生成谈判策略
- 风险项分级: 必须坚持 / 重点谈判 / 可以妥协
- 每个风险项: 谈判立场、底线、建议话术、交换条件
"""
import logging
from typing import List, Dict
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class NegotiationStance(str, Enum):
    INSIST = "insist"
    PUSH_BACK = "push_back"
    NEGOTIATE = "negotiate"
    COMPROMISE = "compromise"
    ACCEPT = "accept"


class RiskCategory(str, Enum):
    LEGAL_VALIDITY = "legal_validity"
    FINANCIAL_EXPOSURE = "financial"
    OPERATIONAL = "operational"
    COMPLIANCE = "compliance"
    COMMERCIAL = "commercial"
    PROCEDURAL = "procedural"


@dataclass
class PlayItem:
    item_id: str
    risk_title: str
    risk_description: str
    original_text: str = ""
    risk_level: str = "medium"
    risk_score: float = 0.0
    category: RiskCategory = RiskCategory.COMMERCIAL
    stance: NegotiationStance = NegotiationStance.NEGOTIATE
    priority: int = 5
    bottom_line: str = ""
    suggested_language: str = ""
    talking_points: List[str] = field(default_factory=list)
    trade_offs: List[str] = field(default_factory=list)
    fallback_position: str = ""
    legal_basis: str = ""


@dataclass
class NegotiationPlaybook:
    contract_title: str = ""
    overall_risk_level: str = "medium"
    overall_risk_score: float = 0.0
    items: List[PlayItem] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)
    opening_statement: str = ""
    negotiation_sequence: List[str] = field(default_factory=list)


class PlaybookGenerator:
    """谈判策略生成器"""

    # 注意: 更具体的关键词排在前面，避免被通用词抢匹配
    RISK_KEYWORD_CATEGORY = [
        # 法律效力 (最严重)
        ('自动续约', RiskCategory.LEGAL_VALIDITY),
        ('连带责任', RiskCategory.LEGAL_VALIDITY),
        ('无限责任', RiskCategory.LEGAL_VALIDITY),
        ('无效', RiskCategory.LEGAL_VALIDITY),
        ('违法', RiskCategory.LEGAL_VALIDITY),
        # 财务 (具体 → 通用)
        ('违约金', RiskCategory.FINANCIAL_EXPOSURE),
        ('赔偿', RiskCategory.FINANCIAL_EXPOSURE),
        ('罚款', RiskCategory.FINANCIAL_EXPOSURE),
        ('付款', RiskCategory.FINANCIAL_EXPOSURE),
        ('金额', RiskCategory.FINANCIAL_EXPOSURE),
        ('价格', RiskCategory.FINANCIAL_EXPOSURE),
        # 合规 (具体 → 通用)
        ('知识产权', RiskCategory.COMPLIANCE),
        ('竞业', RiskCategory.COMPLIANCE),
        ('保密', RiskCategory.COMPLIANCE),
        # 运营 (具体 → 通用)
        ('验收标准', RiskCategory.OPERATIONAL),
        ('质保', RiskCategory.OPERATIONAL),
        ('交付', RiskCategory.OPERATIONAL),
        ('验收', RiskCategory.OPERATIONAL),
        ('期限', RiskCategory.OPERATIONAL),
        # 程序 (最后)
        ('管辖', RiskCategory.PROCEDURAL),
        ('仲裁', RiskCategory.PROCEDURAL),
        ('争议', RiskCategory.PROCEDURAL),
        ('通知', RiskCategory.PROCEDURAL),
        ('送达', RiskCategory.PROCEDURAL),
    ]

    TALKING_POINTS = {
        RiskCategory.LEGAL_VALIDITY: [
            "此条款可能违反《民法典》强制性规定，存在被认定无效的风险",
            "建议参照行业标准做法进行调整，以保障双方合法权益",
            "此条款如发生争议，法院可能不予支持",
        ],
        RiskCategory.FINANCIAL_EXPOSURE: [
            "该金额/费率超出市场合理范围，建议参考行业平均水平",
            "此条款可能导致我方承担不合理的财务风险",
            "建议设置合理的上限或分阶段支付机制",
            "该付款/结算周期在实际操作中难以满足，建议延长",
        ],
        RiskCategory.OPERATIONAL: [
            "该期限在实际操作中难以满足，建议预留合理缓冲",
            "此标准在现有资源条件下难以达成",
            "建议分阶段设定目标，降低单次履约风险",
        ],
        RiskCategory.COMPLIANCE: [
            "此条款可能不符合相关监管要求",
            "建议参照最新法规进行调整",
            "合规风险可能引发行政处罚",
        ],
        RiskCategory.COMMERCIAL: [
            "该条款对双方权利义务的分配不够均衡",
            "建议参考市场惯例进行调整",
            "可以在其他条款上给予对方补偿",
        ],
        RiskCategory.PROCEDURAL: [
            "该程序性条款可以灵活调整",
            "建议选择对双方都便利的方案",
            "此条款不影响核心权益，可作为谈判筹码",
        ],
    }

    def __init__(self):
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"PLAY-{self._counter:03d}"

    def generate(self, risk_findings: List[Dict],
                 contract_title: str = "",
                 overall_risk_score: float = 0.0) -> NegotiationPlaybook:
        if not risk_findings:
            return NegotiationPlaybook(contract_title=contract_title)

        items = []
        for finding in risk_findings:
            item = self._build_play_item(finding)
            items.append(item)

        items.sort(key=lambda x: (x.stance != NegotiationStance.INSIST, -x.priority))

        insist_items = [i for i in items if i.stance == NegotiationStance.INSIST]
        push_items = [i for i in items if i.stance == NegotiationStance.PUSH_BACK]
        negotiate_items = [i for i in items if i.stance == NegotiationStance.NEGOTIATE]
        compromise_items = [i for i in items if i.stance == NegotiationStance.COMPROMISE]
        accept_items = [i for i in items if i.stance == NegotiationStance.ACCEPT]

        sequence = []
        sequence.extend([i.item_id for i in compromise_items])
        sequence.extend([i.item_id for i in negotiate_items])
        sequence.extend([i.item_id for i in push_items])
        sequence.extend([i.item_id for i in insist_items])

        opening = self._generate_opening(items)

        summary = {
            "total_items": len(items),
            "by_stance": {},
            "by_category": {},
            "insist_count": len(insist_items),
            "push_back_count": len(push_items),
            "negotiate_count": len(negotiate_items),
            "compromise_count": len(compromise_items),
            "accept_count": len(accept_items),
            "trade_off_pool": [],
        }
        for item in items:
            summary["by_stance"][item.stance.value] = summary["by_stance"].get(item.stance.value, 0) + 1
            summary["by_category"][item.category.value] = summary["by_category"].get(item.category.value, 0) + 1
            if item.trade_offs:
                summary["trade_off_pool"].extend(item.trade_offs)

        overall_level = "high" if overall_risk_score >= 70 else "medium" if overall_risk_score >= 40 else "low"

        return NegotiationPlaybook(
            contract_title=contract_title,
            overall_risk_level=overall_level,
            overall_risk_score=overall_risk_score,
            items=items,
            summary=summary,
            opening_statement=opening,
            negotiation_sequence=sequence,
        )

    def _build_play_item(self, finding: Dict) -> PlayItem:
        title = finding.get("title", finding.get("risk_title", ""))
        description = finding.get("description", finding.get("risk_description", ""))
        risk_level = finding.get("risk_level", "medium")
        risk_score = finding.get("risk_score", finding.get("combined_risk_score", 50))
        suggestion = finding.get("suggestion", "")
        original_text = finding.get("original_text", finding.get("clause_content", ""))

        category = self._classify_risk(title, description)
        stance = self._determine_stance(category, risk_level)
        priority = self._calc_priority(category, risk_level)
        bottom_line = self._generate_bottom_line(category, risk_level)
        suggested_language = suggestion or self._generate_suggested_language(category, title)
        talking_points = self._generate_talking_points(category, title, description)
        trade_offs = self._generate_trade_offs(stance)
        fallback = self._generate_fallback(stance)
        legal_basis = finding.get("legal_basis", "")

        return PlayItem(
            item_id=self._next_id(),
            risk_title=title,
            risk_description=description,
            original_text=original_text,
            risk_level=risk_level,
            risk_score=float(risk_score) if risk_score else 0.0,
            category=category,
            stance=stance,
            priority=priority,
            bottom_line=bottom_line,
            suggested_language=suggested_language,
            talking_points=talking_points,
            trade_offs=trade_offs,
            fallback_position=fallback,
            legal_basis=legal_basis,
        )

    def _classify_risk(self, title: str, description: str) -> RiskCategory:
        combined = title + description
        for keyword, category in self.RISK_KEYWORD_CATEGORY:
            if keyword in combined:
                return category
        return RiskCategory.COMMERCIAL

    def _determine_stance(self, category: RiskCategory, risk_level: str) -> NegotiationStance:
        if category == RiskCategory.LEGAL_VALIDITY:
            return NegotiationStance.INSIST
        if risk_level == "high" and category in (RiskCategory.FINANCIAL_EXPOSURE, RiskCategory.COMPLIANCE):
            return NegotiationStance.PUSH_BACK
        if risk_level == "high":
            return NegotiationStance.NEGOTIATE
        if risk_level == "medium":
            return NegotiationStance.NEGOTIATE
        if category == RiskCategory.PROCEDURAL:
            return NegotiationStance.COMPROMISE
        return NegotiationStance.ACCEPT

    def _calc_priority(self, category: RiskCategory, risk_level: str) -> int:
        base = {
            RiskCategory.LEGAL_VALIDITY: 10,
            RiskCategory.FINANCIAL_EXPOSURE: 8,
            RiskCategory.COMPLIANCE: 7,
            RiskCategory.OPERATIONAL: 6,
            RiskCategory.COMMERCIAL: 5,
            RiskCategory.PROCEDURAL: 3,
        }.get(category, 5)
        if risk_level == "high":
            base = min(10, base + 2)
        elif risk_level == "low":
            base = max(1, base - 2)
        return base

    def _generate_bottom_line(self, category: RiskCategory, risk_level: str) -> str:
        if category == RiskCategory.LEGAL_VALIDITY:
            return "必须修改或删除，不可保留原条款"
        elif category == RiskCategory.FINANCIAL_EXPOSURE:
            if risk_level == "high":
                return "金额/费率必须降至市场合理范围，否则不同意签署"
            return "可接受小幅调整，但需设置上限"
        elif category == RiskCategory.COMPLIANCE:
            return "必须符合法律法规要求，不可妥协"
        elif category == RiskCategory.OPERATIONAL:
            return "可接受合理延期，但需明确违约责任"
        elif category == RiskCategory.COMMERCIAL:
            return "可作为整体谈判的交换筹码"
        else:
            return "可灵活调整，不影响核心利益"

    def _generate_suggested_language(self, category: RiskCategory, title: str) -> str:
        if category == RiskCategory.LEGAL_VALIDITY:
            return f"建议删除或按《民法典》相关规定重新拟定「{title}」条款"
        elif category == RiskCategory.FINANCIAL_EXPOSURE:
            return f"建议将「{title}」相关金额/费率调整为市场合理水平，并设置上限"
        elif category == RiskCategory.OPERATIONAL:
            return f"建议将「{title}」相关期限延长至合理范围，并增加缓冲期"
        elif category == RiskCategory.COMPLIANCE:
            return f"建议按最新法规要求修改「{title}」条款"
        elif category == RiskCategory.PROCEDURAL:
            return f"建议选择对双方都便利的「{title}」方案"
        else:
            return f"建议就「{title}」进行友好协商，寻求双方都能接受的方案"

    def _generate_talking_points(self, category: RiskCategory, title: str, description: str) -> List[str]:
        points = list(self.TALKING_POINTS.get(category, self.TALKING_POINTS[RiskCategory.COMMERCIAL]))
        points.append(f"关于「{title}」: {description[:80]}")
        return points[:4]

    def _generate_trade_offs(self, stance: NegotiationStance) -> List[str]:
        if stance in (NegotiationStance.INSIST, NegotiationStance.PUSH_BACK):
            return [
                "可在付款方式上给予对方更优惠的条件",
                "可在合同期限上适当让步",
                "可增加合作范围或采购量作为交换",
            ]
        elif stance == NegotiationStance.NEGOTIATE:
            return [
                "可在其他非核心条款上让步",
                "可提供更灵活的履约方案",
            ]
        return []

    def _generate_fallback(self, stance: NegotiationStance) -> str:
        if stance == NegotiationStance.INSIST:
            return "无次选方案，此为底线条款"
        elif stance == NegotiationStance.PUSH_BACK:
            return "如对方坚持，可接受增加对等义务或设置日落条款"
        elif stance == NegotiationStance.NEGOTIATE:
            return "可接受部分修改，换取对方在其他条款上的让步"
        else:
            return "可接受对方方案"

    def _generate_opening(self, items: List[PlayItem]) -> str:
        insist = [i for i in items if i.stance == NegotiationStance.INSIST]
        push = [i for i in items if i.stance == NegotiationStance.PUSH_BACK]
        negotiate = [i for i in items if i.stance == NegotiationStance.NEGOTIATE]

        parts = []
        if insist:
            titles = "、".join([i.risk_title for i in insist[:3]])
            parts.append(f"底线条款（不可退让）: {titles}")
        if push:
            titles = "、".join([i.risk_title for i in push[:3]])
            parts.append(f"重点谈判条款: {titles}")
        if negotiate:
            titles = "、".join([i.risk_title for i in negotiate[:3]])
            parts.append(f"可协商条款: {titles}")

        strategy = "；".join(parts) if parts else "建议逐条友好协商"
        return f"谈判策略: 先谈可协商条款建立合作氛围，再谈重点条款，最后谈底线。{strategy}。"

    def to_dict(self, playbook: NegotiationPlaybook) -> Dict:
        return {
            "contract_title": playbook.contract_title,
            "overall_risk_level": playbook.overall_risk_level,
            "overall_risk_score": playbook.overall_risk_score,
            "opening_statement": playbook.opening_statement,
            "negotiation_sequence": playbook.negotiation_sequence,
            "summary": playbook.summary,
            "items": [
                {
                    "item_id": i.item_id,
                    "risk_title": i.risk_title,
                    "risk_description": i.risk_description,
                    "risk_level": i.risk_level,
                    "risk_score": i.risk_score,
                    "category": i.category.value,
                    "stance": i.stance.value,
                    "priority": i.priority,
                    "bottom_line": i.bottom_line,
                    "suggested_language": i.suggested_language,
                    "talking_points": i.talking_points,
                    "trade_offs": i.trade_offs,
                    "fallback_position": i.fallback_position,
                    "legal_basis": i.legal_basis,
                }
                for i in playbook.items
            ],
        }


def generate_playbook(risk_findings: List[Dict],
                      contract_title: str = "",
                      overall_risk_score: float = 0.0) -> Dict:
    """便捷函数"""
    gen = PlaybookGenerator()
    playbook = gen.generate(risk_findings, contract_title, overall_risk_score)
    return gen.to_dict(playbook)
