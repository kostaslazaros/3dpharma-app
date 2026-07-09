"""
Build a compact `condition_labels.json` from the FREE openFDA drug label API.

The main DrugBank-derived database has drug-drug interactions but no structured
condition contraindications (pregnancy, renal/hepatic impairment, G6PD, etc.).
The openFDA drug label API (https://api.fda.gov/drug/label.json) exposes exactly
those label sections for free. This script pulls the relevant sections for a list
of drugs and writes a small JSON file the backend loads at startup.

Usage:
    python build_condition_labels.py                       # curated seed list
    python build_condition_labels.py --drugs warfarin aspirin
    python build_condition_labels.py --from-db ../comprehensive_drug_database_compact.json --limit 500
    python build_condition_labels.py --out ../data/condition_labels.json

Set OPENFDA_API_KEY in the environment to raise the rate limit (optional).
The script is resumable: existing entries in the output file are kept and skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

API_URL = "https://api.fda.gov/drug/label.json"

# Label sections we care about for co-administration / contraindication checks.
# Superset of prescription (SPL) and OTC label field names.
SECTION_FIELDS = [
    "boxed_warning",
    "contraindications",
    "warnings",
    "warnings_and_cautions",
    "drug_interactions",
    "use_in_specific_populations",
    "pregnancy",
    "pregnancy_or_breast_feeding",
    "nursing_mothers",
    "pediatric_use",
    "geriatric_use",
    "adverse_reactions",
    "do_not_use",
    "ask_doctor",
    "ask_doctor_or_pharmacist",
    "stop_use",
    "when_using",
]

MAX_SECTION_CHARS = 4000  # keep the file small; truncate long narrative sections

# A curated seed list of common active substances so the feature works
# out-of-the-box without downloading the huge OpenFDA/DrugBank dumps.
SEED_DRUGS = [
    "warfarin", "aspirin", "ibuprofen", "naproxen", "diclofenac", "indomethacin",
    "paracetamol", "acetaminophen", "codeine", "tramadol", "morphine", "fentanyl",
    "lisinopril", "enalapril", "ramipril", "losartan", "valsartan", "amlodipine",
    "metoprolol", "atenolol", "propranolol", "bisoprolol", "carvedilol",
    "furosemide", "hydrochlorothiazide", "spironolactone",
    "metformin", "glibenclamide", "gliclazide", "insulin", "sitagliptin",
    "atorvastatin", "simvastatin", "rosuvastatin", "pravastatin",
    "omeprazole", "pantoprazole", "esomeprazole", "ranitidine",
    "amoxicillin", "azithromycin", "ciprofloxacin", "levofloxacin",
    "clarithromycin", "doxycycline", "trimethoprim", "nitrofurantoin",
    "metronidazole", "clindamycin",
    "prednisone", "prednisolone", "dexamethasone", "hydrocortisone",
    "sertraline", "fluoxetine", "citalopram", "escitalopram", "paroxetine",
    "amitriptyline", "venlafaxine", "mirtazapine",
    "diazepam", "lorazepam", "alprazolam", "clonazepam", "zolpidem",
    "carbamazepine", "valproate", "phenytoin", "lamotrigine", "levetiracetam",
    "digoxin", "amiodarone", "clopidogrel", "heparin", "enoxaparin",
    "rivaroxaban", "apixaban", "dabigatran",
    "levothyroxine", "allopurinol", "colchicine", "methotrexate",
    "azathioprine", "tacrolimus", "cyclosporine",
    "salbutamol", "albuterol", "montelukast", "theophylline",
    "cetirizine", "loratadine", "diphenhydramine",
    "primaquine", "chloroquine", "hydroxychloroquine", "dapsone",
    "sulfamethoxazole", "rifampin", "isoniazid",
]


def _http_get_json(url: str, timeout: int = 30) -> Optional[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "3dpharma-condition-labels/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None  # no label found for this drug
        print(f"  ! HTTP {exc.code} for {url}", file=sys.stderr)
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"  ! error: {exc}", file=sys.stderr)
        return None


def _first_text(value) -> str:
    """openFDA returns most sections as a list of strings; join and truncate."""
    if isinstance(value, list):
        text = " ".join(str(v).strip() for v in value if v)
    elif isinstance(value, str):
        text = value.strip()
    else:
        text = ""
    return text[:MAX_SECTION_CHARS]


def _clean_names(values) -> List[str]:
    if isinstance(values, list):
        return [str(v).strip() for v in values if isinstance(v, str) and v.strip()]
    if isinstance(values, str) and values.strip():
        return [values.strip()]
    return []


def fetch_label(drug: str, api_key: Optional[str]) -> Optional[Dict]:
    """Fetch one label for a drug, trying generic then brand name."""
    for field in ("openfda.generic_name", "openfda.brand_name", "openfda.substance_name"):
        params = {"search": f'{field}:"{drug}"', "limit": "1"}
        if api_key:
            params["api_key"] = api_key
        url = f"{API_URL}?{urllib.parse.urlencode(params)}"
        data = _http_get_json(url)
        results = (data or {}).get("results") or []
        if results:
            return results[0]
    return None


def extract_entry(drug: str, raw: Dict) -> Optional[Dict]:
    openfda_meta = raw.get("openfda", {}) or {}
    sections = {}
    for field in SECTION_FIELDS:
        text = _first_text(raw.get(field))
        if text:
            sections[field] = text
    if not sections:
        return None
    return {
        "drug_name": drug,
        "generic_names": _clean_names(openfda_meta.get("generic_name")),
        "brand_names": _clean_names(openfda_meta.get("brand_name")),
        "substance_names": _clean_names(openfda_meta.get("substance_name")),
        "sections": sections,
    }


def load_drug_list(args) -> List[str]:
    if args.drugs:
        return args.drugs
    if args.from_db:
        with open(args.from_db, "r", encoding="utf-8") as f:
            data = json.load(f)
        drugs = [d.get("name") for d in data.get("drugs", []) if d.get("name")]
        if args.limit:
            drugs = drugs[: args.limit]
        return drugs
    return SEED_DRUGS


def main() -> None:
    parser = argparse.ArgumentParser(description="Build condition_labels.json from openFDA")
    parser.add_argument("--drugs", nargs="*", help="explicit list of drug names")
    parser.add_argument("--from-db", help="path to comprehensive_drug_database_compact.json")
    parser.add_argument("--limit", type=int, default=0, help="cap number of drugs from --from-db")
    default_out = os.path.join(os.path.dirname(__file__), "..", "data", "condition_labels.json")
    parser.add_argument("--out", default=default_out, help="output JSON path")
    parser.add_argument("--sleep", type=float, default=0.3, help="seconds between requests")
    args = parser.parse_args()

    api_key = os.getenv("OPENFDA_API_KEY") or None
    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Resume: keep existing entries
    labels: Dict[str, Dict] = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                labels = json.load(f).get("labels", {})
            print(f"Resuming: {len(labels)} existing entries")
        except Exception:  # noqa: BLE001
            labels = {}

    drugs = load_drug_list(args)
    print(f"Fetching openFDA labels for {len(drugs)} drugs -> {out_path}")

    fetched = 0
    for i, drug in enumerate(drugs, 1):
        key = drug.lower().strip()
        if key in labels:
            continue
        raw = fetch_label(drug, api_key)
        if raw:
            entry = extract_entry(drug, raw)
            if entry:
                labels[key] = entry
                fetched += 1
                print(f"  [{i}/{len(drugs)}] {drug}: {len(entry['sections'])} sections")
            else:
                print(f"  [{i}/{len(drugs)}] {drug}: label found but no relevant sections")
        else:
            print(f"  [{i}/{len(drugs)}] {drug}: no label")
        time.sleep(args.sleep)

    output = {
        "metadata": {
            "source": "openFDA drug label API (https://api.fda.gov/drug/label.json)",
            "count": len(labels),
            "section_fields": SECTION_FIELDS,
        },
        "labels": labels,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=1)
    print(f"Done. {fetched} new, {len(labels)} total -> {out_path}")


if __name__ == "__main__":
    main()
