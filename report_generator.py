"""
report_generator.py
--------------------
End-to-end reporting pipeline:

    inventory  ->  validation  ->  risk scoring  ->  HF enrichment
               ->  styled HTML report  +  machine-readable JSON summary

Outputs:
    ai_risk_report.html   -- stakeholder-ready, color-coded report
    ai_risk_summary.json  -- structured feed for downstream systems / audits
"""

import json
import os
from datetime import date

from jinja2 import Environment, FileSystemLoader

from inventory_client import fetch_inventory, validate_inventory, _use_airtable
from risk_engine import apply_risk_scores
from huggingface_enricher import enrich_hf_systems

# Toggle: HF enrichment makes live network calls. Set ENRICH_HF=false to skip
# (useful in CI or offline). Defaults to on.
ENRICH_HF = os.getenv("ENRICH_HF", "true").lower() in {"1", "true", "yes"}


def _flags_to_str(value):
    if isinstance(value, list):
        return ", ".join(value) if value else "None"
    return value if value else "None"


def generate_report():
    df = fetch_inventory()
    dq_issues = validate_inventory(df)
    scored = apply_risk_scores(df)

    # Risk distribution ordered from most to least severe
    band_order = ["Critical", "High", "Medium", "Low"]
    counts = scored["risk_band"].value_counts().to_dict()
    risk_distribution = {b: int(counts.get(b, 0)) for b in band_order}

    report_df = scored.copy()
    report_df["regulatory_flags"] = report_df["regulatory_flags"].apply(_flags_to_str)
    # risk_band is a pandas Categorical; cast to str before filling blanks
    report_df["risk_band"] = report_df["risk_band"].astype(str)

    systems_data = report_df[[
        "system_id", "system_name", "business_unit",
        "composite_risk_score", "risk_band", "decision_impact",
        "regulatory_flags", "owner_email",
    ]].astype(object)
    systems_data = systems_data.where(systems_data.notna(), "UNASSIGNED")
    systems_records = systems_data.to_dict("records")

    # Optional third-party model enrichment
    hf_metadata = []
    if ENRICH_HF:
        try:
            hf_df = enrich_hf_systems(df)
            if not hf_df.empty:
                hf_metadata = hf_df.to_dict("records")
        except Exception as exc:  # noqa: BLE001
            print(f"[report] HF enrichment skipped: {exc}")

    data_source = "Airtable (live)" if _use_airtable() else "Local sample CSV"

    # ---- HTML report ----
    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    template = env.get_template("report_template.html")
    html_output = template.render(
        report_date=date.today().isoformat(),
        total_systems=len(scored),
        data_source=data_source,
        risk_distribution=risk_distribution,
        dq_issues=dq_issues,
        systems=systems_records,
        hf_metadata=hf_metadata,
    )
    with open("ai_risk_report.html", "w", encoding="utf-8") as f:
        f.write(html_output)

    # ---- JSON summary ----
    json_summary = {
        "report_date": date.today().isoformat(),
        "data_source": data_source,
        "total_systems": int(len(scored)),
        "risk_distribution": risk_distribution,
        "data_quality_issues": dq_issues,
        "top_5_critical_systems": [
            {
                "system_id": s["system_id"],
                "system_name": s["system_name"],
                "composite_risk_score": s["composite_risk_score"],
                "risk_band": s["risk_band"],
                "regulatory_flags": s["regulatory_flags"],
                "owner_email": s["owner_email"],
            }
            for s in systems_records
            if s["risk_band"] in ("Critical", "High")
        ][:5],
    }
    with open("ai_risk_summary.json", "w", encoding="utf-8") as f:
        json.dump(json_summary, f, indent=2)

    print("Report generated: ai_risk_report.html")
    print("JSON summary:      ai_risk_summary.json")
    print(f"Risk distribution: {risk_distribution}")
    if dq_issues:
        print(f"Warning: {len(dq_issues)} data-quality field(s) flagged in report.")


if __name__ == "__main__":
    generate_report()
