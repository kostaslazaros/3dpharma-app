"""
Co-administration orchestration — the clinical counterpart to the 3D-printing
compatibility checker. Combines:

  1. Drug-drug interactions   (reuses DrugService.check_compatibility)
  2. Condition contraindications (condition_service, from openFDA labels)
  3. Adverse effects            (condition_service, from openFDA labels)

Returns three galinos-style buckets. Used by both the REST endpoint and the
tool-using AI agent, so the two always agree.
"""

from __future__ import annotations

from typing import Dict, List

from app.services.drug_service import get_drug_service
from app.services import condition_service as cs
from app.services.severity_classifier import get_severity_emoji

DISCLAIMER = (
    "This tool provides informational drug data derived from openFDA product "
    "labels and DrugBank. It is a decision-support aid, not a substitute for the "
    "clinical judgement of a qualified healthcare professional. Always verify "
    "against the approved product information before prescribing or dispensing."
)

_SEVERITY_RANK = {'severe': 0, 'moderate': 1, 'minor': 2, 'unknown': 3}


def _sort_hits(hits: List[Dict]) -> List[Dict]:
    return sorted(hits, key=lambda h: _SEVERITY_RANK.get(h.get('severity', 'unknown'), 3))


def _dedupe(hits: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for h in hits:
        key = (tuple(sorted(h.get('drugs', []))), h.get('condition'), h.get('description', '')[:80])
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def _interaction_hits(service, drugs: List[str]) -> List[Dict]:
    """Pairwise drug-drug interactions via the existing compatibility engine."""
    hits: List[Dict] = []
    for i in range(len(drugs)):
        for j in range(i + 1, len(drugs)):
            d1, d2 = drugs[i], drugs[j]
            try:
                result = service.check_compatibility(d1, d2)
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(result, dict) or result.get('error'):
                continue
            for inter in result.get('interactions', []):
                severity = inter.get('severity', 'moderate')
                hits.append({
                    'drugs': [d1, d2],
                    'condition': None,
                    'condition_label': None,
                    'description': inter.get('description', ''),
                    'severity': severity,
                    'emoji': get_severity_emoji(severity),
                    'source': inter.get('source') or 'DrugBank',
                    'category': 'interaction',
                })
    return hits


def check_coadministration(drugs: List[str], patient: Dict) -> Dict:
    """
    Run a full co-administration check.

    Args:
        drugs: list of drug / active-substance names.
        patient: dict with optional keys sex, age, conditions (list), diseases (list).

    Returns a dict matching the CoAdminResult schema.
    """
    service = get_drug_service()
    patient = patient or {}
    conditions = [c for c in (patient.get('conditions') or []) if c in cs.VALID_CONDITIONS]
    diseases = patient.get('diseases') or []

    # Resolve drug names against the database. A drug counts as resolved if it is
    # in the DrugBank compact index OR has openFDA label data (condition checks
    # only need the latter; drug-drug interactions need the former).
    resolved, unresolved = [], []
    for name in drugs:
        match = service.find_drug(name)
        if match:
            resolved.append(match['name'])
        elif service.get_label_sections(name):
            resolved.append(name)
        else:
            unresolved.append(name)

    interactions = _interaction_hits(service, resolved) if len(resolved) >= 2 else []

    contraindications: List[Dict] = []
    adverse_effects: List[Dict] = []
    for drug in resolved:
        sections = service.get_label_sections(drug)
        if not sections:
            continue
        for cond in conditions:
            hit = cs.assess_condition(drug, sections, cond)
            if hit:
                contraindications.append(hit)
        contraindications.extend(cs.scan_diseases(drug, sections, diseases))
        adverse_effects.extend(cs.extract_adverse_effects(drug, sections, limit=2))

    interactions = _sort_hits(_dedupe(interactions))
    contraindications = _sort_hits(_dedupe(contraindications))
    adverse_effects = _sort_hits(_dedupe(adverse_effects))

    summary = _build_summary(resolved, unresolved, contraindications, interactions, conditions)

    return {
        'drugs': drugs,
        'resolved_drugs': resolved,
        'unresolved_drugs': unresolved,
        'patient': {
            'sex': patient.get('sex'),
            'age': patient.get('age'),
            'conditions': conditions,
            'diseases': diseases,
        },
        'contraindications': contraindications,
        'interactions': interactions,
        'adverse_effects': adverse_effects,
        'summary': summary,
        'disclaimer': DISCLAIMER,
    }


def _build_summary(resolved, unresolved, contraindications, interactions, conditions) -> str:
    parts = []
    if resolved:
        parts.append(f"Checked {len(resolved)} drug(s): {', '.join(resolved)}.")
    if unresolved:
        parts.append(f"Not found in database: {', '.join(unresolved)}.")
    severe_contra = sum(1 for h in contraindications if h['severity'] == 'severe')
    severe_inter = sum(1 for h in interactions if h['severity'] == 'severe')
    if severe_contra:
        parts.append(f"{severe_contra} high-severity contraindication(s) flagged.")
    if severe_inter:
        parts.append(f"{severe_inter} high-severity drug-drug interaction(s) flagged.")
    if not contraindications and not interactions:
        parts.append("No contraindications or interactions found for the given inputs.")
    return ' '.join(parts)
