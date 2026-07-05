# Enterprise AI Inventory & Governance Tracker

A Python governance tool that inventories AI systems across a simulated financial-services
enterprise, pulls third-party risk signals via API, scores each system's risk posture, and
generates stakeholder-ready reports. Built to mirror the day-to-day work of an **AI Risk
Management Analyst**: maintaining visibility into AI deployments, assessing risk, and
communicating findings to leadership in a structured, auditable way.

The design is aligned with the **NIST AI Risk Management Framework** (Map / Measure / Manage)
and models the regulatory context of a firm like Lincoln Financial (FCRA, SOX, HIPAA).

## What it does

1. **Inventory** — loads a structured AI-system inventory (schema in `schema_design.md`).
2. **Validate** — surfaces data-quality gaps (missing owners, unclassified data) before they become audit findings.
3. **Enrich** — pulls live HuggingFace model-card metadata for third-party models.
4. **Score** — computes a weighted composite risk score (0–100) and risk band per system.
5. **Report** — renders a color-coded HTML report + machine-readable JSON summary.
6. **Automate** — a GitHub Actions workflow regenerates and publishes the report weekly.

## Runs with zero accounts

The pipeline ships with a 12-system sample inventory (`data/sample_inventory.csv`) and runs
entirely offline against it. Airtable and HuggingFace are **optional** upgrades — add keys to
`.env` when you want live data.

## Quick start

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the individual stages
python inventory_client.py          # load + validate inventory
python risk_engine.py               # rank systems by composite risk
python huggingface_enricher.py      # pull live model metadata (HF systems)

# Run the full pipeline -> ai_risk_report.html + ai_risk_summary.json
python report_generator.py
```

Open `ai_risk_report.html` in a browser to see the color-coded risk report.

## Switching to live Airtable

1. Create a base called **Enterprise AI Inventory** with a table **AI Systems**, using the
   fields in `schema_design.md`.
2. Copy `.env.example` to `.env` and fill in `AIRTABLE_API_KEY` and `AIRTABLE_BASE_ID`.
3. Set `INVENTORY_SOURCE=airtable` (or leave `auto` — it uses Airtable automatically once keys exist).

## Data source control (`INVENTORY_SOURCE`)

| Value | Behavior |
|-------|----------|
| `auto` (default) | Use Airtable if keys are present, otherwise the sample CSV. |
| `csv` | Always use the local sample CSV. |
| `airtable` | Force Airtable (errors if keys are missing). |

## Project layout

```
ai-governance-tracker/
├── schema_design.md            # Inventory schema (NIST AI RMF-aligned)
├── data/sample_inventory.csv   # 12-system sample inventory
├── inventory_client.py         # Load + validate (CSV fallback + Airtable)
├── huggingface_enricher.py     # Third-party model-card enrichment
├── risk_engine.py              # Weighted composite risk scoring
├── report_generator.py         # HTML + JSON report pipeline
├── templates/report_template.html
├── .github/workflows/governance_report.yml   # Scheduled CI + GitHub Pages
├── GOVERNANCE_MEMO.md          # Executive memo from the sample findings
├── requirements.txt
├── .env.example
└── .gitignore
```

## Security

Secrets live only in `.env` (git-ignored). In CI they are provided as GitHub repository
secrets. No credentials are ever committed.
