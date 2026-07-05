"""
risk_engine.py
--------------
Computes a composite risk score (0-100) for each AI system from weighted,
governance-relevant attributes, then assigns a risk band. This is the logic
that would feed a leadership dashboard or audit-committee report.

Scoring model
-------------
Each attribute contributes a 0-100 sub-score (higher = riskier). Sub-scores
are combined as a weighted average using WEIGHTS. Any value not found in a
SCORING_MAP defaults to 50 (unknown => treated as moderate risk, never
silently zero), which also gently penalizes missing data.
"""

import pandas as pd

WEIGHTS = {
    "risk_tier": 30,
    "decision_impact": 25,
    "data_classification": 20,
    "pii_involved": 15,
    "explainability_method": 10,
}

SCORING_MAPS = {
    "risk_tier": {1: 100, 2: 75, 3: 50, 4: 25},
    "decision_impact": {
        "Automated-High": 100,
        "Automated-Low": 60,
        "Advisory": 30,
    },
    "data_classification": {
        "Restricted": 100,
        "Confidential": 75,
        "Internal": 40,
        "Public": 10,
    },
    "pii_involved": {True: 100, False: 0},
    "explainability_method": {
        "None": 100,
        "Proprietary": 70,
        "LIME": 40,
        "SHAP": 20,
    },
}


def _normalize_value(attribute, value):
    """Make Int64/NA-safe keys for dict lookups."""
    if attribute == "risk_tier":
        try:
            if pd.isna(value):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
    if attribute == "pii_involved":
        return bool(value) if value is not None and not pd.isna(value) else None
    return value


def score_system(row: pd.Series) -> float:
    total_score = 0
    total_weight = 0
    for attribute, weight in WEIGHTS.items():
        value = _normalize_value(attribute, row.get(attribute))
        mapping = SCORING_MAPS.get(attribute, {})
        score = mapping.get(value, 50)  # unknown => moderate risk
        total_score += score * weight
        total_weight += weight
    return round(total_score / total_weight, 1)


def apply_risk_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["composite_risk_score"] = df.apply(score_system, axis=1)
    df["risk_band"] = pd.cut(
        df["composite_risk_score"],
        bins=[0, 30, 55, 75, 100],
        labels=["Low", "Medium", "High", "Critical"],
        include_lowest=True,
    )
    return df.sort_values("composite_risk_score", ascending=False)


if __name__ == "__main__":
    from inventory_client import fetch_inventory

    df = fetch_inventory()
    scored = apply_risk_scores(df)
    cols = ["system_id", "system_name", "composite_risk_score", "risk_band"]
    print(scored[cols].to_string(index=False))
