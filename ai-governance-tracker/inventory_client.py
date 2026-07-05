"""
inventory_client.py
--------------------
Loads the AI system inventory into a pandas DataFrame.

Two data sources are supported:

1. Airtable (live)  -- used automatically when AIRTABLE_API_KEY and
   AIRTABLE_BASE_ID are present in the environment / .env file.
2. Local CSV (fallback) -- used when Airtable credentials are absent, or
   when INVENTORY_SOURCE=csv is set. This lets the whole pipeline run and
   be tested with zero external accounts.

The DataFrame shape is identical regardless of source, so every downstream
module (risk engine, enricher, report generator) works either way.
"""

import os
import ast

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "AI Systems")
INVENTORY_SOURCE = os.getenv("INVENTORY_SOURCE", "auto").lower()

# Path to the bundled sample inventory used as the offline fallback.
CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_inventory.csv")

# Airtable boolean/list fields need light normalization so the CSV and API
# sources produce identical Python types.
BOOL_FIELDS = ["pii_involved"]
LIST_FIELDS = ["regulatory_flags"]


def _use_airtable() -> bool:
    """Decide which source to read from."""
    if INVENTORY_SOURCE == "csv":
        return False
    if INVENTORY_SOURCE == "airtable":
        return True
    # auto: use Airtable only if we actually have credentials
    return bool(AIRTABLE_API_KEY and BASE_ID)


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "checked"}
    return bool(value)


def _coerce_list(value):
    """Normalize regulatory_flags into a clean list of strings."""
    if isinstance(value, list):
        items = value
    elif value is None or (isinstance(value, float) and pd.isna(value)):
        items = []
    elif isinstance(value, str):
        raw = value.strip()
        if not raw or raw.lower() == "none":
            items = []
        elif raw.startswith("["):  # stringified list
            try:
                items = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                items = [raw]
        else:
            # support ';' or ',' separated multi-selects from the CSV
            sep = ";" if ";" in raw else ","
            items = [p.strip() for p in raw.split(sep) if p.strip()]
    else:
        items = [value]
    return [str(i).strip() for i in items if str(i).strip().lower() != "none"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    for field in BOOL_FIELDS:
        if field in df.columns:
            df[field] = df[field].apply(_coerce_bool)
    for field in LIST_FIELDS:
        if field in df.columns:
            df[field] = df[field].apply(_coerce_list)
    if "risk_tier" in df.columns:
        df["risk_tier"] = pd.to_numeric(df["risk_tier"], errors="coerce").astype("Int64")
    return df


def fetch_inventory_from_csv(path: str = CSV_PATH) -> pd.DataFrame:
    """Load the inventory from the bundled sample CSV."""
    # keep_default_na=False so the literal string "None" (a valid value for
    # explainability_method) is NOT silently converted to NaN by pandas.
    # Truly empty cells become "" and are caught by validate_inventory().
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])
    df.insert(0, "record_id", [f"csv-{i}" for i in range(len(df))])
    return _normalize(df)


def fetch_inventory_from_airtable() -> pd.DataFrame:
    """Load the inventory from Airtable, following pagination."""
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
    records, params = [], {}

    while True:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        for record in data.get("records", []):
            flat = {"record_id": record["id"]}
            flat.update(record.get("fields", {}))
            records.append(flat)

        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset

    return _normalize(pd.DataFrame(records))


def fetch_inventory() -> pd.DataFrame:
    """Fetch the inventory from whichever source is configured/available."""
    if _use_airtable():
        try:
            df = fetch_inventory_from_airtable()
            print(f"[inventory] Loaded {len(df)} systems from Airtable.")
            return df
        except Exception as exc:  # noqa: BLE001 - fall back gracefully
            print(f"[inventory] Airtable fetch failed ({exc}); using local CSV.")
    df = fetch_inventory_from_csv()
    print(f"[inventory] Loaded {len(df)} systems from local sample CSV.")
    return df


def validate_inventory(df: pd.DataFrame) -> dict:
    """Surface data-quality gaps the way a governance analyst would."""
    required_fields = [
        "system_id",
        "system_name",
        "risk_tier",
        "data_classification",
        "owner_email",
        "regulatory_flags",
    ]
    issues = {}
    for field in required_fields:
        if field not in df.columns:
            issues[field] = "Column missing entirely"
            continue

        if field == "regulatory_flags":
            # empty list counts as unclassified
            empty_mask = df[field].apply(lambda v: not v if isinstance(v, list) else pd.isna(v))
        else:
            empty_mask = df[field].isna() | (df[field].astype(str).str.strip() == "")

        offenders = df[empty_mask]
        if len(offenders):
            names = offenders["system_id"].tolist() if "system_id" in df.columns else []
            issues[field] = {
                "count": int(len(offenders)),
                "message": f"{len(offenders)} record(s) missing this field",
                "system_ids": names,
            }
    return issues


if __name__ == "__main__":
    df = fetch_inventory()
    print(f"\nFetched {len(df)} AI systems from inventory.")
    issues = validate_inventory(df)
    if issues:
        print("\nData Quality Issues Detected:")
        for field, issue in issues.items():
            detail = issue["message"] if isinstance(issue, dict) else issue
            ids = ", ".join(issue["system_ids"]) if isinstance(issue, dict) else ""
            print(f"  - {field}: {detail}" + (f"  [{ids}]" if ids else ""))
    else:
        print("Data quality check passed. All required fields populated.")
