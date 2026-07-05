"""
huggingface_enricher.py
-----------------------
For every inventory system whose model_source is 'HuggingFace', pull live
model-card metadata from the public HuggingFace API. This simulates
integrating a third-party AI risk signal (license, provenance, freshness)
into the central tracker.

The HuggingFace models API is public; HUGGINGFACE_API_TOKEN is optional and
only raises rate limits. The enricher works with or without it.
"""

import os

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
HF_HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}


def fetch_model_metadata(model_id: str) -> dict:
    """Return normalized model-card metadata for a HuggingFace model id."""
    url = f"https://huggingface.co/api/models/{model_id}"
    try:
        response = requests.get(url, headers=HF_HEADERS, timeout=30)
    except requests.RequestException as exc:
        return {"model_id": model_id, "error": str(exc), "status": "network_error"}

    if response.status_code != 200:
        return {
            "model_id": model_id,
            "error": f"Could not fetch model {model_id}",
            "status": response.status_code,
        }

    data = response.json()
    card = data.get("cardData") or {}
    return {
        "model_id": model_id,
        "downloads_last_month": data.get("downloads", "N/A"),
        "likes": data.get("likes", "N/A"),
        "pipeline_tag": data.get("pipeline_tag", "Unknown"),
        "last_modified": data.get("lastModified", "Unknown"),
        "has_model_card": bool(card),
        "license": card.get("license", "Not specified"),
        "tags": data.get("tags", []),
    }


def enrich_hf_systems(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich all HuggingFace-sourced systems in the inventory."""
    if "model_source" not in df.columns:
        return pd.DataFrame()

    hf_systems = df[df["model_source"] == "HuggingFace"].copy()
    enriched_rows = []

    for _, row in hf_systems.iterrows():
        # For HuggingFace systems the 'vendor' field stores the model repo id.
        model_ref = str(row.get("vendor", "")).strip()
        if not model_ref:
            continue
        metadata = fetch_model_metadata(model_ref)
        metadata["system_id"] = row.get("system_id")
        metadata["system_name"] = row.get("system_name")
        enriched_rows.append(metadata)

    return pd.DataFrame(enriched_rows) if enriched_rows else pd.DataFrame()


if __name__ == "__main__":
    from inventory_client import fetch_inventory

    df = fetch_inventory()
    enriched = enrich_hf_systems(df)
    if enriched.empty:
        print("No HuggingFace-sourced systems found in inventory.")
    else:
        print(enriched.to_string(index=False))
