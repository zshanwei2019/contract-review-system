"""
义务提取 + 履约跟踪服务
- 从合同条款中提取结构化义务 (谁、做什么、什么时候)
- 生成履约时间线
- 到期/逾期提醒
"""
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class ObligationType(str, Enum):
    PAYMENT = "payment"
    DELIVERY = "delivery"
    INSPECTION = "inspection"
    NOTICE = "notice"
    CONFIDENTIALITY = "confidentiality"
    NON_COMPETE = "non_compete"
    WARRANTY = "warranty"
    INSURANCE = "insurance"
    OTHER = "other"


class ObligationStatus(str, Enum):
    PENDING = "pending"
    UPCOMING = "upcoming"
    OVERDUE = "overdue"
    FULFILLED = "fulfilled"
    CONDITIONAL = "conditional"


@dataclass
class Obligation:
    obligation_id: str
    obligation_type: ObligationType
    party: str
    action: str
    deadline: Optional[str] = None
    deadline_text: str = ""
    amount: Optional[float] = None
    currency: str = "CNY"
    conditions: List[str] = field(default_factory=list)
    penalty: str = ""
    source_clause: int = 0
    source_text: str = ""
    status: ObligationStatus = ObligationStatus.PENDING
    risk_level: str = "low"


@dataclass
class ObligationTimeline:
    contract_id: int
    contract_title: str = ""
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    obligations: List[Obligation] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)


class ObligationExtractor:
    """义务提取引擎"""

    OBLIGATION_PATTERNS = {
        ObligationType.PAYMENT: [
            (r'(甲方|乙方|买方|卖方|需方|供方|出租方|承租方)\s*(?:应|应当|须|必须|负责)\s*(?:在|于)?\s*[^。；\n]{0,30}?(?:支付|付款|缴纳|付清|结清)', 'payment'),
            (r'(?:支付|付款|缴纳).*?(?:期限|时间|日期).*?[：:]\s*(.+?)(?:[。；\n]|$)', 'payment_deadline'),
            (r'(?:甲方|乙方).*?(?:在|于).*?(?:收到|验收|交付).*?后\s*(\d+)\s*(?:个?[日月]|天|工作日).*?(?:支付|付款)', 'payment_conditional'),
        ],
        ObligationType.DELIVERY: [
            (r'(甲方|乙方|买方|卖方|供方)\s*(?:应|应当|须|必须|负责)\s*[^。；\n]{0,30}?(?:交付|交货|发货|送货|运输|配送)', 'delivery'),
            (r'(?:在|于)\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)\s*(?:前|之前|以前).*?(?:交付|交货|完成)', 'delivery_date'),
        ],
        ObligationType.INSPECTION: [
            (r'(甲方|乙方|买方)\s*(?:应|应当|须|必须|负责)\s*[^。；\n]{0,30}?(?:验收|检验|检查|检测)', 'inspection'),
            (r'(?:收到|交付).*?后\s*(\d+)\s*(?:个?[日月]|天|工作日).*?(?:验收|检验)', 'inspection_conditional'),
        ],
        ObligationType.NOTICE: [
            (r'(甲方|乙方)\s*(?:应|应当|须|必须)\s*[^。；\n]{0,30}?(?:通知|告知|通报|报告|送达)', 'notice'),
            (r'(?:通知|告知).*?(?:在|于|提前)\s*(\d+)\s*(?:个?[日月]|天|工作日)', 'notice_deadline'),
        ],
        ObligationType.CONFIDENTIALITY: [
            (r'(甲方|乙方)\s*(?:应|应当|须|必须)\s*[^。；\n]{0,30}?(?:保密|不得泄露|不得披露|不得公开)', 'confidentiality'),
        ],
        ObligationType.NON_COMPETE: [
            (r'(甲方|乙方)\s*(?:应|应当|须|必须)\s*[^。；\n]{0,30}?(?:竞业|不得从事|不得经营|不得兼职)', 'non_compete'),
        ],
        ObligationType.WARRANTY: [
            (r'(甲方|乙方|供方|卖方)\s*(?:应|应当|须|必须|负责)\s*[^。；\n]{0,30}?(?:质保|保修|维修|维护|保养)', 'warranty'),
            (r'(?:质保|保修).*?(?:期|期限).*?(?:为|不少于)\s*(\d+)\s*(?:个?[月年]|天)', 'warranty_term'),
        ],
        ObligationType.INSURANCE: [
            (r'(甲方|乙方)\s*(?:应|应当|须|必须)\s*[^。；\n]{0,30}?(?:投保|购买.*保险|办理.*保险)', 'insurance'),
        ],
    }

    TIME_PATTERNS = [
        (r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', 'absolute'),
        (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', 'absolute'),
        (r'(\d+)\s*个?\s*工作日\s*(?:内|之内|以内)', 'relative_workday'),
        (r'(\d+)\s*个?\s*[日月]\s*(?:内|之内|以内)', 'relative_day'),
        (r'(\d+)\s*个?\s*月\s*(?:内|之内|以内)', 'relative_month'),
        (r'收到.*?后\s*(\d+)\s*(?:个?[日月]|天|工作日)', 'after_receipt'),
        (r'验收.*?后\s*(\d+)\s*(?:个?[日月]|天|工作日)', 'after_inspection'),
    ]

    def __init__(self):
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"OBL-{self._counter:03d}"

    def extract(self, clauses: List[Dict], contract_sign_date: Optional[str] = None) -> ObligationTimeline:
        obligations = []
        effective_date = None
        expiry_date = None

        for clause in clauses:
            content = clause.get("content", "")
            idx = clause.get("index", 0)

            if not effective_date:
                m = re.search(r'(?:有效期|合同期限).*?自\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)', content)
                if m:
                    effective_date = self._normalize_date(m.group(1))
            if not expiry_date:
                m = re.search(r'(?:有效期|合同期限).*?至\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)', content)
                if m:
                    expiry_date = self._normalize_date(m.group(1))

            for obl_type, patterns in self.OBLIGATION_PATTERNS.items():
                for pattern, _ in patterns:
                    for m in re.finditer(pattern, content):
                        obl = self._parse_match(m, obl_type, idx, content)
                        if obl:
                            obligations.append(obl)
                            break

        obligations = self._deduplicate(obligations)

        sign_date = contract_sign_date or effective_date
        for obl in obligations:
            if obl.deadline_text and not obl.deadline:
                obl.deadline = self._calculate_deadline(obl.deadline_text, sign_date)

        today = date.today().isoformat()
        for obl in obligations:
            if obl.deadline:
                if obl.deadline < today:
                    obl.status = ObligationStatus.OVERDUE
                elif obl.deadline <= (date.today() + timedelta(days=7)).isoformat():
                    obl.status = ObligationStatus.UPCOMING

        summary = {
            "total_obligations": len(obligations),
            "by_type": {},
            "by_party": {},
            "by_status": {},
            "overdue_count": 0,
            "upcoming_count": 0,
            "payment_total": 0.0,
        }
        for obl in obligations:
            summary["by_type"][obl.obligation_type.value] = summary["by_type"].get(obl.obligation_type.value, 0) + 1
            summary["by_party"][obl.party] = summary["by_party"].get(obl.party, 0) + 1
            summary["by_status"][obl.status.value] = summary["by_status"].get(obl.status.value, 0) + 1
            if obl.status == ObligationStatus.OVERDUE:
                summary["overdue_count"] += 1
            elif obl.status == ObligationStatus.UPCOMING:
                summary["upcoming_count"] += 1
            if obl.amount:
                summary["payment_total"] += obl.amount

        return ObligationTimeline(
            contract_id=0,
            effective_date=effective_date,
            expiry_date=expiry_date,
            obligations=obligations,
            summary=summary,
        )

    def _parse_match(self, m, obl_type, clause_idx, full_content):
        matched_text = m.group(0).strip()
        if len(matched_text) < 5:
            return None

        party = "未知"
        if m.lastindex and m.lastindex >= 1:
            pt = m.group(1)
            if pt in ('甲方', '买方', '需方', '出租方'):
                party = "甲方"
            elif pt in ('乙方', '卖方', '供方', '承租方'):
                party = "乙方"

        # 提取金额 (只提取明确是金额的，排除日期数字)
        amount = None
        # 金额关键词 + 数字
        amt_match = re.search(r'(?:人民币|￥|¥|RMB)\s*([\d,]+\.?\d*)\s*(?:万|元|万元|亿)?', matched_text)
        if not amt_match:
            amt_match = re.search(r'([\d,]+\.?\d*)\s*(?:万|元|万元|亿)\s*(?:人民币|￥|¥|RMB)?', matched_text)
        if not amt_match:
            amt_match = re.search(r'(?:金额|总价|价款|费用|报酬|租金|货款|违约金|赔偿|罚款)\s*[：:]*\s*([\d,]+\.?\d*)\s*(?:万|元|万元|亿)?', matched_text)
        if amt_match:
            try:
                nums = re.findall(r'[\d,]+\.?\d*', amt_match.group())
                if nums:
                    amount = float(nums[0].replace(',', ''))
                    if '万' in amt_match.group():
                        amount *= 10000
                    if '亿' in amt_match.group():
                        amount *= 100000000
            except ValueError:
                pass

        deadline_text = ""
        for time_pat, _ in self.TIME_PATTERNS:
            tm = re.search(time_pat, matched_text)
            if tm:
                deadline_text = tm.group(0).strip()
                break

        penalty = ""
        pm = re.search(r'(?:否则|逾期|违约).*?(?:支付|赔偿|承担|罚款).*?(?:[。；\n]|$)', full_content)
        if pm:
            penalty = pm.group(0).strip()[:100]

        conditions = []
        cm = re.search(r'(?:在|于|待|等)\s*(.+?)\s*(?:后|之后|完成|完毕)', matched_text)
        if cm:
            conditions.append(cm.group(1).strip())

        return Obligation(
            obligation_id=self._next_id(),
            obligation_type=obl_type,
            party=party,
            action=matched_text[:200],
            deadline_text=deadline_text,
            amount=amount,
            conditions=conditions,
            penalty=penalty,
            source_clause=clause_idx,
            source_text=full_content[max(0, m.start()-30):min(len(full_content), m.end()+50)].strip(),
            status=ObligationStatus.PENDING,
        )

    def _deduplicate(self, obligations):
        seen = {}
        for obl in obligations:
            key = (obl.obligation_type.value, obl.source_clause)
            if key not in seen:
                seen[key] = obl
            else:
                existing = seen[key]
                if len(obl.action) > len(existing.action):
                    seen[key] = obl
                if obl.deadline_text and not existing.deadline_text:
                    seen[key] = obl
        return list(seen.values())

    def _normalize_date(self, text):
        m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', text)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        return None

    def _calculate_deadline(self, deadline_text, sign_date):
        """根据期限文本和签订日期计算截止日期"""
        if not sign_date:
            return None

        # 绝对日期
        m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', deadline_text)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        # 相对日期
        try:
            base = date.fromisoformat(sign_date)
        except (ValueError, TypeError):
            return None

        m = re.search(r'(\d+)\s*个?\s*工作日', deadline_text)
        if m:
            days = int(m.group(1))
            # 简化: 工作日 ≈ 日历日 * 1.4
            return (base + timedelta(days=int(days * 1.4))).isoformat()

        m = re.search(r'(\d+)\s*个?\s*[日月]', deadline_text)
        if m:
            return (base + timedelta(days=int(m.group(1)))).isoformat()

        m = re.search(r'(\d+)\s*个?\s*月', deadline_text)
        if m:
            months = int(m.group(1))
            new_month = base.month + months
            new_year = base.year + (new_month - 1) // 12
            new_month = ((new_month - 1) % 12) + 1
            new_day = min(base.day, 28)
            return f"{new_year}-{new_month:02d}-{new_day:02d}"

        return None

    def to_dict(self, timeline: ObligationTimeline) -> Dict:
        return {
            "contract_id": timeline.contract_id,
            "effective_date": timeline.effective_date,
            "expiry_date": timeline.expiry_date,
            "summary": timeline.summary,
            "obligations": [
                {
                    "obligation_id": o.obligation_id,
                    "obligation_type": o.obligation_type.value,
                    "party": o.party,
                    "action": o.action,
                    "deadline": o.deadline,
                    "deadline_text": o.deadline_text,
                    "amount": o.amount,
                    "conditions": o.conditions,
                    "penalty": o.penalty,
                    "source_clause": o.source_clause,
                    "source_text": o.source_text,
                    "status": o.status.value,
                    "risk_level": o.risk_level,
                }
                for o in timeline.obligations
            ],
        }


def extract_obligations(clauses: List[Dict], sign_date: Optional[str] = None) -> Dict:
    """便捷函数"""
    extractor = ObligationExtractor()
    timeline = extractor.extract(clauses, sign_date)
    return extractor.to_dict(timeline)
