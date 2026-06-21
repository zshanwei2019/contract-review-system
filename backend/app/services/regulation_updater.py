"""
法规动态更新服务 (Regulation Updater)
- 法规数据库管理（民法典、公司法、劳动法等）
- 法规变更检测与通知
- 合同条款合规性校验（基于最新法规）
- 法规影响评估
"""
import re
import json
import logging
import hashlib
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Regulation:
    """法规条目"""
    id: str
    name: str  # 法规名称
    article: str  # 条款编号
    content: str  # 条款内容
    category: str  # 分类: civil/commercial/labor/tax/ip
    effective_date: str  # 生效日期
    status: str = "active"  # active/amended/repealed
    amended_date: Optional[str] = None
    keywords: List[str] = field(default_factory=list)


# 法规数据库（模拟，实际可接入北大法宝/威科先行API）
REGULATION_DB: List[Regulation] = [
    # 民法典 - 合同编
    Regulation(
        id="civil-470",
        name="中华人民共和国民法典",
        article="第四百七十条",
        content="合同的内容由当事人约定，一般包括下列条款：（一）当事人的姓名或者名称和住所；（二）标的；（三）数量；（四）质量；（五）价款或者报酬；（六）履行期限、地点和方式；（七）违约责任；（八）解决争议的方法。当事人可以参照各类合同的示范文本订立合同。",
        category="civil",
        effective_date="2021-01-01",
        keywords=["合同内容", "合同条款", "必备条款"],
    ),
    Regulation(
        id="civil-496",
        name="中华人民共和国民法典",
        article="第四百九十六条",
        content="格式条款是当事人为了重复使用而预先拟定，并在订立合同时未与对方协商的条款。采用格式条款订立合同的，提供格式条款的一方应当遵循公平原则确定当事人之间的权利和义务，并采取合理的方式提示对方注意免除或者减轻其责任等与对方有重大利害关系的条款，按照对方的要求，对该条款予以说明。提供格式条款的一方未履行提示或者说明义务，致使对方没有注意或者理解与其有重大利害关系的条款的，对方可以主张该条款不成为合同的内容。",
        category="civil",
        effective_date="2021-01-01",
        keywords=["格式条款", "提示义务", "说明义务", "免责条款"],
    ),
    Regulation(
        id="civil-497",
        name="中华人民共和国民法典",
        article="第四百九十七条",
        content="有下列情形之一的，该格式条款无效：（一）具有本法第一编第六章第三节和本法第五百零六条规定的无效情形；（二）提供格式条款一方不合理地免除或者减轻其责任、加重对方责任、限制对方主要权利；（三）提供格式条款一方排除对方主要权利。",
        category="civil",
        effective_date="2021-01-01",
        keywords=["格式条款无效", "免责", "加重责任", "排除权利"],
    ),
    Regulation(
        id="civil-506",
        name="中华人民共和国民法典",
        article="第五百零六条",
        content="合同中的下列免责条款无效：（一）造成对方人身损害的；（二）因故意或者重大过失造成对方财产损失的。",
        category="civil",
        effective_date="2021-01-01",
        keywords=["免责条款无效", "人身损害", "重大过失"],
    ),
    Regulation(
        id="civil-563",
        name="中华人民共和国民法典",
        article="第五百六十三条",
        content="有下列情形之一的，当事人可以解除合同：（一）因不可抗力致使不能实现合同目的；（二）在履行期限届满前，当事人一方明确表示或者以自己的行为表明不履行主要债务；（三）当事人一方迟延履行主要债务，经催告后在合理期限内仍未履行；（四）当事人一方迟延履行债务或者有其他违约行为致使不能实现合同目的；（五）法律规定的其他情形。以持续履行的债务为内容的不定期合同，当事人可以随时解除合同，但是应当在合理期限之前通知对方。",
        category="civil",
        effective_date="2021-01-01",
        keywords=["合同解除", "不可抗力", "违约", "根本违约"],
    ),
    Regulation(
        id="civil-577",
        name="中华人民共和国民法典",
        article="第五百七十七条",
        content="当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。",
        category="civil",
        effective_date="2021-01-01",
        keywords=["违约责任", "继续履行", "赔偿损失"],
    ),
    Regulation(
        id="civil-584",
        name="中华人民共和国民法典",
        article="第五百八十四条",
        content="当事人一方不履行合同义务或者履行合同义务不符合约定，造成对方损失的，损失赔偿额应当相当于因违约所造成的损失，包括合同履行后可以获得的利益；但是，不得超过违约方订立合同时预见到或者应当预见到的因违约可能造成的损失。",
        category="civil",
        effective_date="2021-01-01",
        keywords=["损失赔偿", "可预见规则", "可得利益"],
    ),
    Regulation(
        id="civil-585",
        name="中华人民共和国民法典",
        article="第五百八十五条",
        content="当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金，也可以约定因违约产生的损失赔偿额的计算方法。约定的违约金低于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以增加；约定的违约金过分高于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以适当减少。",
        category="civil",
        effective_date="2021-01-01",
        keywords=["违约金", "违约金调整", "过高违约金"],
    ),
    # 公司法
    Regulation(
        id="company-16",
        name="中华人民共和国公司法",
        article="第十六条",
        content="公司向其他企业投资或者为他人提供担保，依照公司章程的规定，由董事会或者股东会、股东大会决议；公司章程对投资或者担保的总额及单项投资或者担保的数额有限额规定的，不得超过规定的限额。公司为公司股东或者实际控制人提供担保的，必须经股东会或者股东大会决议。前款规定的股东或者受前款规定的实际控制人支配的股东，不得参加前款规定事项的表决。该项表决由出席会议的其他股东所持表决权的过半数通过。",
        category="commercial",
        effective_date="2024-07-01",
        keywords=["公司担保", "关联担保", "股东会决议"],
    ),
    # 劳动合同法
    Regulation(
        id="labor-38",
        name="中华人民共和国劳动合同法",
        article="第三十八条",
        content="用人单位有下列情形之一的，劳动者可以解除劳动合同：（一）未按照劳动合同约定提供劳动保护或者劳动条件的；（二）未及时足额支付劳动报酬的；（三）未依法为劳动者缴纳社会保险费的；（四）用人单位的规章制度违反法律、法规的规定，损害劳动者权益的；（五）因本法第二十六条第一款规定的情形致使劳动合同无效的；（六）法律、行政法规规定劳动者可以解除劳动合同的其他情形。用人单位以暴力、威胁或者非法限制人身自由的手段强迫劳动者劳动的，或者用人单位违章指挥、强令冒险作业危及劳动者人身安全的，劳动者可以立即解除劳动合同，不需事先告知用人单位。",
        category="labor",
        effective_date="2008-01-01",
        keywords=["劳动者解除", "拖欠工资", "社保", "强迫劳动"],
    ),
    Regulation(
        id="labor-47",
        name="中华人民共和国劳动合同法",
        article="第四十七条",
        content="经济补偿按劳动者在本单位工作的年限，每满一年支付一个月工资的标准向劳动者支付。六个月以上不满一年的，按一年计算；不满六个月的，向劳动者支付半个月工资的经济补偿。劳动者月工资高于用人单位所在直辖市、设区的市级人民政府公布的本地区上年度职工月平均工资三倍的，向其支付经济补偿的标准按职工月平均工资三倍的数额支付，向其支付经济补偿的年限最高不超过十二年。本条所称月工资是指劳动者在劳动合同解除或者终止前十二个月的平均工资。",
        category="labor",
        effective_date="2008-01-01",
        keywords=["经济补偿", "N+1", "解除劳动合同", "工作年限"],
    ),
]


# 法规变更日志（模拟）
REGULATION_CHANGES = [
    {
        "id": "change-2024-company",
        "regulation": "中华人民共和国公司法",
        "change_type": "amended",
        "effective_date": "2024-07-01",
        "summary": "2023年修订版公司法于2024年7月1日施行，涉及注册资本认缴制、公司治理结构、董监高责任等重大修改",
        "affected_articles": ["第十六条", "第二十三条", "第四十七条"],
        "impact": "high",
    },
    {
        "id": "change-2021-civil",
        "regulation": "中华人民共和国民法典",
        "change_type": "new",
        "effective_date": "2021-01-01",
        "summary": "民法典正式施行，合同法、物权法、侵权责任法等九部法律同时废止",
        "affected_articles": [],
        "impact": "high",
    },
]


def search_regulations(query: str, category: Optional[str] = None) -> List[Regulation]:
    """
    搜索相关法规

    Args:
        query: 搜索关键词
        category: 法规分类过滤 (civil/commercial/labor/tax/ip)

    Returns:
        匹配的法规列表
    """
    results = []
    query_lower = query.lower()

    for reg in REGULATION_DB:
        if category and reg.category != category:
            continue

        # 关键词匹配
        score = 0
        if query_lower in reg.content.lower():
            score += 3
        if query_lower in reg.name.lower():
            score += 2
        if query_lower in reg.article.lower():
            score += 1
        for kw in reg.keywords:
            if query_lower in kw.lower():
                score += 2
                break

        if score > 0:
            results.append((score, reg))

    results.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in results[:10]]


def check_clause_compliance(
    clause_text: str,
    contract_type: str = "other",
) -> List[Dict]:
    """
    检查合同条款是否符合最新法规

    Args:
        clause_text: 条款文本
        contract_type: 合同类型

    Returns:
        合规性问题列表
    """
    issues = []

    # 检查格式条款风险
    if any(kw in clause_text for kw in ["最终解释权", "恕不另行通知", "本公司有权单方面"]):
        issues.append({
            "type": "format_clause_risk",
            "severity": "high",
            "regulation": "民法典第四百九十六条、第四百九十七条",
            "description": "可能存在无效格式条款，建议删除或修改",
            "suggestion": "格式条款应遵循公平原则，对重大利害关系条款履行提示说明义务",
        })

    # 检查违约金是否过高
    penalty_match = re.search(r'违约金.*?(\d+)%', clause_text)
    if penalty_match:
        pct = int(penalty_match.group(1))
        if pct > 30:
            issues.append({
                "type": "excessive_penalty",
                "severity": "high",
                "regulation": "民法典第五百八十五条",
                "description": f"违约金比例{pct}%可能被认定为过高",
                "suggestion": "建议将违约金比例控制在合理范围内（通常不超过实际损失的30%）",
            })

    # 检查免责条款
    if any(kw in clause_text for kw in ["概不负责", "不承担任何责任", "免除一切责任"]):
        issues.append({
            "type": "invalid_disclaimer",
            "severity": "high",
            "regulation": "民法典第五百零六条",
            "description": "完全免除责任的条款可能无效",
            "suggestion": "免责条款不得免除人身损害责任及故意或重大过失造成的财产损失责任",
        })

    # 检查担保条款（公司合同）
    if contract_type in ("guarantee", "loan") and "担保" in clause_text:
        issues.append({
            "type": "guarantee_compliance",
            "severity": "medium",
            "regulation": "公司法第十六条",
            "description": "公司对外担保需经董事会或股东会决议",
            "suggestion": "建议要求对方提供有效的股东会/董事会决议文件",
        })

    # 检查竞业限制（劳动合同）
    if contract_type == "labor" and "竞业限制" in clause_text:
        has_compensation = any(kw in clause_text for kw in ["补偿", "补偿金", "经济补偿"])
        if not has_compensation:
            issues.append({
                "type": "non_compete_no_compensation",
                "severity": "high",
                "regulation": "劳动合同法第二十三条",
                "description": "竞业限制条款未约定经济补偿",
                "suggestion": "竞业限制期间应按月给予劳动者经济补偿，不低于劳动合同履行地最低工资标准",
            })

    return issues


def check_full_contract_compliance(
    full_text: str,
    contract_type: str = "other",
) -> Dict:
    """
    全合同合规性检查

    Args:
        full_text: 完整合同文本
        contract_type: 合同类型

    Returns:
        合规检查结果
    """
    all_issues = []
    related_regulations = set()

    # 按段落检查
    paragraphs = re.split(r'\n\s*\n', full_text)
    for para in paragraphs:
        if len(para.strip()) < 20:
            continue
        issues = check_clause_compliance(para, contract_type)
        for issue in issues:
            issue["context"] = para.strip()[:200]
        all_issues.extend(issues)
        for issue in issues:
            if "regulation" in issue:
                related_regulations.add(issue["regulation"])

    # 搜索相关法规
    relevant_regs = []
    for reg_name in related_regulations:
        for reg in REGULATION_DB:
            if reg.name in reg_name:
                relevant_regs.append({
                    "name": reg.name,
                    "article": reg.article,
                    "content": reg.content[:200],
                    "effective_date": reg.effective_date,
                })
                break

    high_count = sum(1 for i in all_issues if i.get("severity") == "high")
    medium_count = sum(1 for i in all_issues if i.get("severity") == "medium")

    return {
        "summary": {
            "total_issues": len(all_issues),
            "risk_distribution": {"high": high_count, "medium": medium_count, "low": 0},
            "overall_risk": "high" if high_count > 0 else ("medium" if medium_count > 2 else "low"),
        },
        "issues": all_issues,
        "related_regulations": relevant_regs,
    }


def get_regulation_updates(since_date: Optional[str] = None) -> List[Dict]:
    """
    获取法规变更

    Args:
        since_date: 起始日期 (YYYY-MM-DD)，默认最近6个月

    Returns:
        法规变更列表
    """
    if since_date:
        cutoff = datetime.strptime(since_date, "%Y-%m-%d")
    else:
        now = datetime.now()
        cutoff_month = now.month - 6
        cutoff_year = now.year
        if cutoff_month <= 0:
            cutoff_month += 12
            cutoff_year -= 1
        cutoff = now.replace(year=cutoff_year, month=cutoff_month)

    updates = []
    for change in REGULATION_CHANGES:
        change_date = datetime.strptime(change["effective_date"], "%Y-%m-%d")
        if change_date >= cutoff:
            updates.append(change)

    return updates


def assess_regulation_impact(
    contract_text: str,
    contract_type: str = "other",
) -> Dict:
    """
    评估法规变更对合同的影响

    Args:
        contract_text: 合同文本
        contract_type: 合同类型

    Returns:
        影响评估结果
    """
    updates = get_regulation_updates()
    impacts = []

    for update in updates:
        # 检查合同是否涉及受影响条款
        affected = False
        matched_articles = []

        for article in update.get("affected_articles", []):
            if article in contract_text:
                affected = True
                matched_articles.append(article)

        # 检查关键词匹配
        if not affected:
            for reg in REGULATION_DB:
                if reg.name == update["regulation"]:
                    for kw in reg.keywords:
                        if kw in contract_text:
                            affected = True
                            matched_articles.append(reg.article)
                            break

        if affected:
            impacts.append({
                "regulation": update["regulation"],
                "change_type": update["change_type"],
                "effective_date": update["effective_date"],
                "summary": update["summary"],
                "matched_articles": matched_articles,
                "impact_level": update["impact"],
                "recommendation": f"建议审查合同相关条款，确保符合{update['regulation']}（{update['effective_date']}施行）的最新规定",
            })

    high_impact = sum(1 for i in impacts if i["impact_level"] == "high")
    medium_impact = sum(1 for i in impacts if i["impact_level"] == "medium")

    return {
        "summary": {
            "total_impacts": len(impacts),
            "high_impact": high_impact,
            "medium_impact": medium_impact,
            "requires_review": len(impacts) > 0,
        },
        "impacts": impacts,
        "checked_regulations": len(updates),
    }
