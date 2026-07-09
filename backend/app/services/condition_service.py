"""
Condition service — maps patient conditions (pregnancy, lactation, renal/hepatic
impairment, alcohol, G6PD deficiency, myelosuppression, driving) to the relevant
openFDA drug-label sections and grades severity.

Data comes from DrugService.get_label_sections() (built by
scripts/build_condition_labels.py). Severity grading reuses the existing
regex engine in severity_classifier so the whole app stays consistent.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.services.severity_classifier import classify_severity, get_severity_emoji

# Sections most likely to mention a contraindicating condition, in priority order.
_CONTRA_SECTIONS = [
    'contraindications', 'boxed_warning', 'warnings_and_cautions', 'warnings',
    'use_in_specific_populations', 'do_not_use', 'drug_interactions',
]

# Patient conditions aligned with galinos.gr crossCheck.
# `sections`  : which label sections to scan (in priority order)
# `patterns`  : regex probes identifying text relevant to the condition
# `direct`    : sections whose mere presence is itself the relevant text
#               (e.g. the "pregnancy" section is inherently about pregnancy)
CONDITIONS: Dict[str, Dict] = {
    'pregnancy': {
        'label': 'Pregnancy',
        'sections': ['pregnancy', 'pregnancy_or_breast_feeding',
                     'use_in_specific_populations'] + _CONTRA_SECTIONS,
        'patterns': [r'\bpregnan', r'\bfetal\b', r'\bfetus\b', r'\bteratogen',
                     r'\bin utero\b', r'\bgestat'],
        'direct': ['pregnancy'],
    },
    'lactation': {
        'label': 'Lactation / breastfeeding',
        'sections': ['nursing_mothers', 'pregnancy_or_breast_feeding',
                     'use_in_specific_populations'] + _CONTRA_SECTIONS,
        'patterns': [r'\blactat', r'\bnursing\b', r'\bbreast[\s-]?feed',
                     r'\bbreast milk\b', r'\bhuman milk\b'],
        'direct': ['nursing_mothers'],
    },
    'renal_impairment': {
        'label': 'Renal impairment',
        'sections': ['use_in_specific_populations'] + _CONTRA_SECTIONS,
        'patterns': [r'\brenal\b', r'\bkidney', r'\bnephro', r'\bcreatinine\b',
                     r'\bcreatinine clearance\b', r'\bcrcl\b', r'\begfr\b',
                     r'\bhemodialysis\b', r'\bdialysis\b'],
        'direct': [],
    },
    'hepatic_impairment': {
        'label': 'Hepatic impairment',
        'sections': ['use_in_specific_populations'] + _CONTRA_SECTIONS,
        'patterns': [r'\bhepatic\b', r'\bliver\b', r'\bcirrhosis\b',
                     r'\bchild[\s-]?pugh\b', r'\bhepatotox', r'\bcholestasis\b'],
        'direct': [],
    },
    'alcohol': {
        'label': 'Alcohol consumption',
        'sections': _CONTRA_SECTIONS + ['adverse_reactions'],
        'patterns': [r'\balcohol', r'\bethanol\b', r'\bdisulfiram', r'\bintoxicat'],
        'direct': [],
    },
    'g6pd_deficiency': {
        'label': 'G6PD deficiency',
        'sections': _CONTRA_SECTIONS,
        'patterns': [r'\bg-?6-?pd\b', r'glucose[\s-]?6[\s-]?phosphate',
                     r'\bhemolytic anemia\b', r'\bhemolysis\b'],
        'direct': [],
    },
    'myelosuppression': {
        'label': 'Myelosuppression / bone marrow suppression',
        'sections': ['boxed_warning'] + _CONTRA_SECTIONS + ['adverse_reactions'],
        'patterns': [r'\bmyelosuppress', r'\bbone marrow\b', r'\bmyelotox',
                     r'\bneutropeni', r'\bagranulocyt', r'\bpancytopeni',
                     r'\bthrombocytopeni', r'\baplastic anemia\b',
                     r'\bleukopeni'],
        'direct': [],
    },
    'driving': {
        'label': 'Driving / operating machinery',
        'sections': _CONTRA_SECTIONS + ['adverse_reactions'],
        'patterns': [r'\bdriv(?:e|ing)\b', r'\bmachinery\b', r'\boperat\w* machin',
                     r'\bsomnolen', r'\bdrowsi', r'\bsedat', r'\bdizzi',
                     r'\bimpair\w* (?:mental|physical|cognit)'],
        'direct': [],
    },
}

VALID_CONDITIONS = set(CONDITIONS.keys())

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9])')
_MAX_SNIPPET = 400


def _sentences(text: str) -> List[str]:
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _find_relevant_snippet(text: str, patterns: List[re.Pattern]) -> Optional[tuple]:
    """
    Find the earliest keyword match.

    Returns (display_snippet, core_text) or None. `display_snippet` keeps a little
    lead context for readability; `core_text` starts at the keyword so the severity
    classifier scores the on-topic text and is not skewed by adjacent wording.
    """
    if not text:
        return None
    earliest: Optional[int] = None
    for pat in patterns:
        m = pat.search(text)
        if m and (earliest is None or m.start() < earliest):
            earliest = m.start()
    if earliest is None:
        return None
    end = min(len(text), earliest + (_MAX_SNIPPET - 40))
    core_text = text[earliest:end].strip()
    start = max(0, earliest - 40)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = '…' + snippet
    if end < len(text):
        snippet = snippet + '…'
        core_text = core_text + '…'
    return snippet, core_text


def _compile(patterns: List[str]) -> List[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


# Pre-compile condition patterns once.
for _cfg in CONDITIONS.values():
    _cfg['_compiled'] = _compile(_cfg['patterns'])


def assess_condition(drug: str, sections: Dict[str, str], condition_key: str) -> Optional[Dict]:
    """
    Assess whether `drug`'s label flags a concern for `condition_key`.
    Returns a structured hit or None if nothing relevant is found.
    """
    cfg = CONDITIONS.get(condition_key)
    if not cfg or not sections:
        return None

    compiled = cfg['_compiled']

    # 1) A dedicated section (e.g. "pregnancy") is inherently relevant.
    for direct in cfg.get('direct', []):
        text = sections.get(direct)
        if text:
            found = _find_relevant_snippet(text, compiled)
            snippet = found[0] if found else text[:_MAX_SNIPPET]
            severity, _ = classify_severity(text)
            return _hit(drug, condition_key, cfg, snippet, severity, direct)

    # 2) Otherwise scan the priority sections for a keyword match.
    for section in cfg['sections']:
        text = sections.get(section)
        if not text:
            continue
        found = _find_relevant_snippet(text, compiled)
        if found:
            snippet, core_text = found
            severity, _ = classify_severity(core_text)
            # A hit inside the contraindications section is at least moderate.
            if section == 'contraindications' and severity in ('minor', 'unknown'):
                severity = 'severe'
            return _hit(drug, condition_key, cfg, snippet, severity, section)

    return None


def scan_diseases(drug: str, sections: Dict[str, str], diseases: List[str]) -> List[Dict]:
    """Scan contraindication/warning sections for user-supplied disease terms."""
    hits: List[Dict] = []
    if not diseases or not sections:
        return hits
    scan_sections = ['contraindications', 'boxed_warning', 'warnings_and_cautions',
                     'warnings', 'do_not_use']
    for disease in diseases:
        term = disease.strip()
        if len(term) < 3:
            continue
        pat = re.compile(r'\b' + re.escape(term), re.IGNORECASE)
        for section in scan_sections:
            text = sections.get(section)
            if not text:
                continue
            found = _find_relevant_snippet(text, [pat])
            if found:
                snippet, core_text = found
                severity, _ = classify_severity(core_text)
                if section in ('contraindications', 'do_not_use') and severity in ('minor', 'unknown'):
                    severity = 'severe'
                hits.append({
                    'drugs': [drug],
                    'condition': f'disease:{term}',
                    'condition_label': term,
                    'description': snippet,
                    'severity': severity,
                    'emoji': get_severity_emoji(severity),
                    'source': f'openFDA label — {section}',
                    'category': 'contraindication',
                })
                break  # one hit per disease is enough
    return hits


def extract_adverse_effects(drug: str, sections: Dict[str, str], limit: int = 3) -> List[Dict]:
    """Surface the most notable adverse reactions from the label."""
    text = sections.get('adverse_reactions') or sections.get('warnings_and_cautions')
    if not text:
        return []
    hits: List[Dict] = []
    for sentence in _sentences(text)[:limit]:
        if len(sentence) < 15:
            continue
        severity, _ = classify_severity(sentence)
        hits.append({
            'drugs': [drug],
            'condition': 'adverse_reaction',
            'condition_label': 'Adverse reaction',
            'description': sentence[:_MAX_SNIPPET],
            'severity': severity,
            'emoji': get_severity_emoji(severity),
            'source': 'openFDA label — adverse_reactions',
            'category': 'adverse_effect',
        })
    return hits


def _hit(drug: str, condition_key: str, cfg: Dict, snippet: str,
         severity: str, section: str) -> Dict:
    return {
        'drugs': [drug],
        'condition': condition_key,
        'condition_label': cfg['label'],
        'description': snippet,
        'severity': severity,
        'emoji': get_severity_emoji(severity),
        'source': f'openFDA label — {section}',
        'category': 'contraindication',
    }
