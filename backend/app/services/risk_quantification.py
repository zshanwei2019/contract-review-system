"""
风险量化评估服务 - 四维加权评估模型
- severity (40%): 严重性 - 风险发生后的损害程度
- likelihood (25%): 可能性 - 风险发生的概率
- financial_exposure (20%): 财务风险敞口 - 潜在经济损失
- responsibility_asymmetry (15%): 责任不对称性 - 合同双方权利义务失衡程度
"""
from typing import Optional

# 默认四维权重
DEFAULT_WEIGHTS = {
    "severity": 0.40,
    "likelihood": 0.25,
    "financial": 0.20,
    "responsibility": 0.15,
}


def calculate_risk_score(
    score_severity: int,
    score_likelihood: int,
    score_financial: int,
    score_responsibility: int,
    weights: Optional[dict] = None,
) -> int:
    """计算综合风险评分 (0-100)"""
    w = weights or DEFAULT_WEIGHTS
    weighted_score = (
        score_severity * w["severity"]
        + score_likelihood * w["likelihood"]
        + score_financial * w["financial"]
        + score_responsibility * w["responsibility"]
    )
    return min(100, max(0, round(weighted_score)))


def determine_risk_level(score: int) -> str:
    """根据综合评分确定风险等级"""
    if score >= 70:
        return "high"
    elif score >= 40:
        return "medium"
    elif score >= 10:
        return "low"
    else:
        return "none"


def calculate_expected_loss(
    potential_loss_max: float,
    loss_probability: float,
) -> float:
    """计算期望损失 = 最大潜在损失 x 损失概率"""
    return round(potential_loss_max * loss_probability, 2)


def generate_quantification_detail(
    score_severity: int,
    score_likelihood: int,
    score_financial: int,
    score_responsibility: int,
    risk_score: int,
    weights: Optional[dict] = None,
) -> dict:
    """生成量化分析详情"""
    w = weights or DEFAULT_WEIGHTS
    return {
        "model": "四维加权评估模型",
        "weights": w,
        "dimensions": {
            "severity": {
                "score": score_severity,
                "weight": w["severity"],
                "weighted_score": round(score_severity * w["severity"], 2),
                "label": "严重性",
                "description": "风险发生后的损害程度",
            },
            "likelihood": {
                "score": score_likelihood,
                "weight": w["likelihood"],
                "weighted_score": round(score_likelihood * w["likelihood"], 2),
                "label": "可能性",
                "description": "风险发生的概率",
            },
            "financial": {
                "score": score_financial,
                "weight": w["financial"],
                "weighted_score": round(score_financial * w["financial"], 2),
                "label": "财务风险敞口",
                "description": "潜在经济损失规模",
            },
            "responsibility": {
                "score": score_responsibility,
                "weight": w["responsibility"],
                "weighted_score": round(score_responsibility * w["responsibility"], 2),
                "label": "责任不对称性",
                "description": "合同双方权利义务失衡程度",
            },
        },
        "total_score": risk_score,
        "risk_level": determine_risk_level(risk_score),
    }


def estimate_financial_impact(
    risk_level: str,
    contract_value: Optional[float] = None,
) -> dict:
    """基于风险等级和合同金额估算财务影响"""
    impact_ratios = {
        "high": {"min_ratio": 0.10, "max_ratio": 0.50, "probability": 0.60},
        "medium": {"min_ratio": 0.03, "max_ratio": 0.15, "probability": 0.30},
        "low": {"min_ratio": 0.01, "max_ratio": 0.05, "probability": 0.10},
        "none": {"min_ratio": 0.0, "max_ratio": 0.01, "probability": 0.02},
    }
    ratio = impact_ratios.get(risk_level, impact_ratios["low"])
    base_value = contract_value or 100000
    return {
        "potential_loss_min": round(base_value * ratio["min_ratio"], 2),
        "potential_loss_max": round(base_value * ratio["max_ratio"], 2),
        "loss_probability": ratio["probability"],
    }


def ai_quantification_prompt(clause_text: str, risk_description: str) -> str:
    """生成AI量化评估提示词"""
    return f"""请对以下合同风险进行量化评估，返回JSON格式结果。

## 风险描述
{risk_description}

## 相关条款
{clause_text}

## 评估要求
请对以下四个维度分别评分(0-100分):

1. **severity (严重性)**: 风险一旦发生，造成的损害程度
   - 90-100: 可能导致公司重大损失、法律诉讼、声誉损害
   - 70-89: 可能导致较大经济损失或业务中断
   - 40-69: 可能导致一定经济损失或运营困难
   - 10-39: 影响较小，可内部消化
   - 0-9: 几乎无实际影响

2. **likelihood (可能性)**: 风险实际发生的概率
   - 90-100: 极高概率发生
   - 70-89: 高概率发生
   - 40-69: 有一定概率发生
   - 10-39: 发生概率较低
   - 0-9: 极小概率发生

3. **financial (财务风险敞口)**: 潜在经济损失规模
   - 90-100: 损失可能超过合同金额50%
   - 70-89: 损失可能在合同金额20-50%
   - 40-69: 损失可能在合同金额5-20%
   - 10-39: 损失可能在合同金额1-5%
   - 0-9: 损失不足合同金额1%

4. **responsibility (责任不对称性)**: 合同双方权利义务失衡程度
   - 90-100: 完全单方面承担风险，对方几乎无责任
   - 70-89: 明显不对等，己方承担大部分风险
   - 40-69: 存在一定不对等，但尚可接受
   - 10-39: 基本对等
   - 0-9: 完全对等

请返回JSON格式:
```json
{{
    "score_severity": <0-100>,
    "score_likelihood": <0-100>,
    "score_financial": <0-100>,
    "score_responsibility": <0-100>,
    "potential_loss_min": <最小潜在损失金额>,
    "potential_loss_max": <最大潜在损失金额>,
    "loss_probability": <0-1之间的小数>,
    "analysis_reasoning": "<简要分析推理过程>"
}}
```"""


def format_risk_report(risk_item) -> str:
    """格式化风险量化报告"""
    level_labels = {"high": "高风险", "medium": "中风险", "low": "低风险", "none": "无风险"}
    level_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢", "none": "⚪"}
    level = risk_item.risk_level.value if hasattr(risk_item.risk_level, 'value') else risk_item.risk_level
    emoji = level_emoji.get(level, "⚪")
    label = level_labels.get(level, "未知")
    report = f"""{emoji} 风险评估报告
━━━━━━━━━━━━━━━━━━
风险等级: {label}
综合评分: {risk_item.risk_score or 'N/A'}/100

📊 四维评分:
  • 严重性: {risk_item.score_severity or 'N/A'}/100
  • 可能性: {risk_item.score_likelihood or 'N/A'}/100
  • 财务敞口: {risk_item.score_financial or 'N/A'}/100
  • 责任不对称: {risk_item.score_responsibility or 'N/A'}/100"""
    if risk_item.potential_loss_max:
        report += f"""

💰 财务影响:
  • 最小损失: ¥{risk_item.potential_loss_min:,.0f}
  • 最大损失: ¥{risk_item.potential_loss_max:,.0f}
  • 损失概率: {risk_item.loss_probability*100:.0f}%
  • 期望损失: ¥{risk_item.expected_loss:,.0f}"""
    return report
