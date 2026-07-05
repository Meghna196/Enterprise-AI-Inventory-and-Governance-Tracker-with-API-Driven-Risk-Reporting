# AI System Inventory Schema v1.0

This schema defines the structured record used to inventory AI systems across the
enterprise. It is intentionally aligned with the **NIST AI Risk Management Framework
(AI RMF 1.0)** — specifically the **MAP** function, which calls for establishing
context and cataloging AI systems and their risk-relevant attributes before they can
be measured and managed. Each field below maps to information a governance analyst
needs to assess risk posture, regulatory exposure, and accountability.

## Core Fields

| Field | Type | Description | NIST AI RMF alignment |
|-------|------|-------------|-----------------------|
| `system_id` | Text (primary) | Unique identifier, e.g. `AIS-001` | MAP 1 — establish system context |
| `system_name` | Text | Human-readable name | MAP 1 |
| `vendor` | Text | Internal team or third-party vendor. For HuggingFace-sourced systems this holds the model repo ID (e.g. `distilbert-base-uncased`). | MAP 4 — third-party / supply-chain risk |
| `model_type` | Single select | Classification, NLP, Regression, Generative, Other | MAP 2 — categorize the AI system |
| `business_unit` | Single select | Owning department: Underwriting, Claims, Marketing, Finance, IT, Compliance | MAP 1 — organizational context |
| `data_classification` | Single select | Public, Internal, Confidential, Restricted | MAP 3 — data sensitivity |
| `deployment_environment` | Single select | Production, Staging, Pilot | MAP 2 — deployment context |
| `decision_impact` | Single select | Advisory, Automated-Low, Automated-High | MAP 5 — impact on individuals / org |
| `last_audit_date` | Date (ISO 8601) | Most recent governance audit | GOVERN — accountability cadence |
| `risk_tier` | Number | 1 (Critical), 2 (High), 3 (Medium), 4 (Low) | MEASURE — inherent risk rating |
| `model_source` | Single select | Internal, HuggingFace, OpenAI, AWS, Azure, Other | MAP 4 — provenance |
| `pii_involved` | Boolean | Whether the system processes personally identifiable information | MAP 3 — privacy exposure |
| `explainability_method` | Single select | SHAP, LIME, None, Proprietary | MEASURE — transparency / interpretability |
| `owner_email` | Email | Accountable system owner | GOVERN — clear ownership |
| `regulatory_flags` | Multiple select | FCRA, HIPAA, SOX, None | MAP 3 — legal/regulatory context |

## Design notes

- **Risk tier vs. composite score.** `risk_tier` is an analyst-assigned *inherent*
  rating captured at intake. The tracker's risk engine computes a separate
  *composite risk score* from weighted attributes so the two can be cross-checked;
  divergence between them is itself a useful review signal.
- **Ownership is a control, not a nicety.** A blank `owner_email` means no one is
  accountable for the system — the validation module flags these as data-quality
  findings before they reach an audit.
- **Regulatory flags drive scope.** For a financial-services firm like Lincoln
  Financial, `FCRA` (adverse-action / credit decisioning) and `SOX` (financial
  reporting integrity) flags determine which controls and evidence an auditor will
  demand. `HIPAA` applies where health data touches insurance underwriting.
- **Provenance enables enrichment.** Systems with `model_source = HuggingFace` are
  enriched with live model-card metadata (license, last-modified, downloads) so that
  third-party model risk is monitored from an authoritative source, not a static note.

## Change control

This schema is versioned. Any field addition, removal, or enum change increments the
version and is committed to version control so the inventory has an auditable history.

_Schema version: 1.0 — established at project inception._
