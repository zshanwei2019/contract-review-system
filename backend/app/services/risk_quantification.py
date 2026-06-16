"""
风险量化评估服务 - 四维加权评估模型
- severity (40%): 严重性 - 风险发生后的损害程度
- likelihood (25%): 可能性 - 风险发生的概率
- financial_exposure (20%): 财务风险敞口 - 潜在经济损失
- responsibility_asymmetry (15%): 责任不对称性 - 合同双方权利义务失衡程度
"""
from typing import Optional


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


def calculate_expected_loss(potential_loss_max: float, loss_probability: float) -> float:
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
            "severity": {"score": score_severity, "weight": w["severity"], "weighted_score": round(score_severity * w["severity"], 2), "label": "严重性"},
            "likelihood": {"score": score_likelihood, "weight": w["likelihood"], "weighted_score": round(score_likelihood * w["likelihood"], 2), "label": "可能性"},
            "financial": {"score": score_financial, "weight": w["financial"], "weighted_score": round(score_financial * w["financial"], 2), "label": "财务风险敞口"},
            "responsibility": {"score": score_responsibility, "weight": w["responsibility"], "weighted_score": round(score_responsibility * w["responsibility"], 2), "label": "责任不对称性"},
        },
        "total_score": risk_score,
        "risk_level": determine_risk_level(risk_score),
    }


def estimate_financial_impact(risk_level: str, contract_value: Optional[float] = None) -> dict:
    """基于风险等级估算财务影响"""
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
