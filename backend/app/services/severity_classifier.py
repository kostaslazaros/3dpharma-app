"""
Severity Classification Module using Regex Patterns

This module classifies drug interaction severity into three categories:
- SEVERE (Red): Life-threatening, contraindicated, or dangerous interactions
- MODERATE (Yellow): Requires monitoring or dose adjustment
- MINOR (Green): Low risk, theoretical, or minimal clinical significance
"""

import re
from typing import Tuple, List, Dict

# =============================================================================
# SEVERE PATTERNS (Red) - Life-threatening or Contraindicated
# =============================================================================
SEVERE_PATTERNS = [
    # Absolute contraindications
    (r'\bcontraindicated\b', 'contraindication'),
    (r'\bshould not be (?:used|combined|given|taken|administered|co-administered)\b', 'should_not'),
    (r'\bmust not\b', 'must_not'),
    (r'\bdo not (?:use|combine|give|take|administer)\b', 'do_not'),
    (r'\bavoid(?:ed|ing)?\b(?! alcohol| grapefruit)', 'avoid'),  # "avoid" but not just food warnings
    (r'\bnever\b', 'never'),
    (r'\bprohibited\b', 'prohibited'),
    (r'\babsolutely\b', 'absolutely'),
    
    # Life-threatening conditions
    (r'\b(?:fatal|death|lethal|life[- ]threatening|mortality)\b', 'fatal'),
    (r'\bdangerous\b', 'dangerous'),
    
    # Cardiac emergencies
    (r'\bcardiac arrest\b', 'cardiac_arrest'),
    (r'\bheart failure\b', 'heart_failure'),
    (r'\bQT[c]?\s*(?:interval\s*)?prolong(?:ation|ed|ing|s)?\b', 'qt_prolongation'),
    (r'\btorsades?\s*(?:de\s*)?pointes?\b', 'torsades'),
    (r'\b(?:ventricular|fatal|serious|severe)\s*arrhythmi(?:a|as)\b', 'arrhythmia_severe'),
    (r'\bbradycardia\b', 'bradycardia'),
    (r'\basystole\b', 'asystole'),
    (r'\bsudden\s*(?:cardiac\s*)?death\b', 'sudden_death'),
    
    # Neurological emergencies
    (r'\bserotonin\s*syndrome\b', 'serotonin_syndrome'),
    (r'\bneuroleptic\s*malignant\s*syndrome\b', 'nms'),
    (r'\bseizure[s]?\b', 'seizure'),
    (r'\bconvulsion[s]?\b', 'convulsion'),
    (r'\bcoma\b', 'coma'),
    (r'\bencephalopathy\b', 'encephalopathy'),
    
    # Respiratory emergencies
    (r'\brespiratory\s*(?:depression|arrest|failure)\b', 'respiratory_depression'),
    (r'\bapn[eo]a\b', 'apnea'),
    
    # Bleeding/Hemorrhage
    (r'\b(?:severe|major|life[- ]threatening|fatal|serious)\s*(?:bleeding|hemorrhag(?:e|ing|ic))\b', 'bleeding_severe'),
    (r'\bintracranial\s*(?:bleeding|hemorrhag(?:e|ing))\b', 'intracranial_bleed'),
    (r'\bgastrointestinal\s*(?:bleeding|hemorrhag(?:e|ing))\b', 'gi_bleed'),
    
    # Blood pressure emergencies
    (r'\bhypertensive\s*crisis\b', 'hypertensive_crisis'),
    (r'\bsevere\s*hypotension\b', 'hypotension_severe'),
    (r'\bhypotensive\s*(?:shock|crisis|collapse)\b', 'hypotensive_shock'),
    
    # Organ toxicity
    (r'\bnephrotoxic(?:ity)?\b', 'nephrotoxicity'),
    (r'\bhepato(?:toxicity|toxic)\b', 'hepatotoxicity'),
    (r'\bcardiotoxic(?:ity)?\b', 'cardiotoxicity'),
    (r'\b(?:acute\s*)?(?:renal|kidney)\s*(?:failure|injury|damage)\b', 'renal_failure'),
    (r'\b(?:acute\s*)?(?:liver|hepatic)\s*(?:failure|injury|damage)\b', 'liver_failure'),
    (r'\brhabdomyolysis\b', 'rhabdomyolysis'),
    
    # Bone marrow / Blood disorders
    (r'\bagranulocytosis\b', 'agranulocytosis'),
    (r'\baplastic\s*anemia\b', 'aplastic_anemia'),
    (r'\bpancytopenia\b', 'pancytopenia'),
    (r'\bthrombocytopenia\b', 'thrombocytopenia'),
    
    # Metabolic emergencies
    (r'\bhyperkalemi(?:a|c)\b', 'hyperkalemia'),
    (r'\bhypoglyc(?:emia|emic)\s*(?:crisis|shock|severe)?\b', 'hypoglycemia'),
    (r'\blactic\s*acidosis\b', 'lactic_acidosis'),
    
    # Anaphylaxis / Severe allergic
    (r'\banaphyla(?:xis|ctic)\b', 'anaphylaxis'),
    (r'\bStevens[- ]Johnson\b', 'stevens_johnson'),
    (r'\btoxic\s*epidermal\s*necrolysis\b', 'ten'),
    (r'\bangioedema\b', 'angioedema'),
    
    # Severity keywords
    (r'\bsevere(?:ly)?\s+(?:increased?|toxic|adverse|harmful)\b', 'severe_effect'),
    (r'\bserious(?:ly)?\s+(?:increased?|toxic|adverse|harmful)\b', 'serious_effect'),
    (r'\bmajor\s+(?:toxicity|adverse|interaction)\b', 'major_effect'),
    (r'\bsignificant(?:ly)?\s+(?:increased?\s+)?risk\b', 'significant_risk'),
]

# =============================================================================
# MINOR PATTERNS (Green) - Low Risk / Theoretical
# =============================================================================
MINOR_PATTERNS = [
    (r'\bminor\s+(?:effect|interaction|change|impact)\b', 'minor_effect'),
    (r'\bmild(?:ly)?\s+(?:increase|decrease|affect|change)\b', 'mild_effect'),
    (r'\bslight(?:ly)?\s+(?:increase|decrease|affect|change)\b', 'slight_effect'),
    (r'\bminimal(?:ly)?\s+(?:clinically\s+)?(?:significant|relevant|important)\b', 'minimal'),
    (r'\bunlikely\s+to\s+(?:be|cause|have|result)\b', 'unlikely'),
    (r'\btheoretical(?:ly)?\b', 'theoretical'),
    (r'\brare(?:ly)?\b', 'rare'),
    (r'\bnot\s+(?:clinically\s+)?(?:significant|relevant|important)\b', 'not_significant'),
    (r'\bnegligible\b', 'negligible'),
    (r'\bno\s+(?:clinically\s+)?significant\s+(?:interaction|effect|change)\b', 'no_significant'),
    (r'\bno\s+(?:dose\s+)?adjustment\s+(?:is\s+)?(?:needed|required|necessary)\b', 'no_adjustment'),
    (r'\bwell[- ]tolerated\b', 'well_tolerated'),
]

# =============================================================================
# MODERATE PATTERNS (Yellow) - Monitor / Adjust / Caution
# =============================================================================
MODERATE_PATTERNS = [
    # Effect changes requiring attention
    (r'\bmay\s+(?:increase|decrease|enhance|reduce|potentiate|inhibit)\s+(?:the\s+)?(?:effect|level|concentration|activity|toxicity|efficacy|risk)\b', 'may_affect'),
    (r'\bcan\s+(?:increase|decrease|enhance|reduce|potentiate|inhibit)\s+(?:the\s+)?(?:effect|level|concentration|activity|toxicity|efficacy|risk)\b', 'can_affect'),
    (r'\b(?:increased?|decreased?|reduced?|enhanced?)\s+(?:effect|level|concentration|activity|toxicity|efficacy)\b', 'changed_effect'),
    (r'\b(?:increased?|elevated?)\s+risk\s+of\b', 'increased_risk'),
    (r'\bdecreased?\s+(?:therapeutic\s+)?efficacy\b', 'decreased_efficacy'),
    
    # Caution / Monitor instructions
    (r'\buse\s+(?:with\s+)?caution\b', 'use_caution'),
    (r'\bcaution\s+(?:is\s+)?(?:advised|recommended|warranted|required)\b', 'caution_advised'),
    (r'\bmonitor(?:ed|ing)?\s+(?:closely|carefully|regularly)?\b', 'monitor'),
    (r'\bclose(?:ly)?\s+monitor(?:ed|ing)?\b', 'close_monitoring'),
    (r'\brequire[s]?\s+monitoring\b', 'requires_monitoring'),
    
    # Dose adjustment
    (r'\bdose\s+(?:adjustment|reduction|modification)\s+(?:may\s+be\s+)?(?:needed|required|necessary|recommended)\b', 'dose_adjustment'),
    (r'\breduce\s+(?:the\s+)?dose\b', 'reduce_dose'),
    (r'\badjust\s+(?:the\s+)?dose\b', 'adjust_dose'),
    (r'\blower\s+dos(?:e|age|ing)\b', 'lower_dose'),
    
    # Pharmacokinetic interactions
    (r'\bpotentiate[s]?\b', 'potentiate'),
    (r'\binhibit[s]?\s+(?:the\s+)?(?:metabolism|clearance|excretion)\b', 'inhibit_metabolism'),
    (r'\binduce[s]?\s+(?:the\s+)?(?:metabolism|clearance|excretion)\b', 'induce_metabolism'),
    (r'\bCYP[0-9A-Z]+\s+(?:inhibit|induc)\b', 'cyp_interaction'),
    (r'\bserum\s+concentration\s+(?:may\s+be\s+)?(?:increased?|decreased?|elevated?|reduced?)\b', 'serum_concentration'),
    (r'\bplasma\s+(?:level|concentration)\s+(?:may\s+be\s+)?(?:increased?|decreased?)\b', 'plasma_level'),
    (r'\bhalf[- ]?life\s+(?:may\s+be\s+)?(?:increased?|decreased?|prolonged?|shortened?)\b', 'half_life'),
    (r'\bclearance\s+(?:may\s+be\s+)?(?:increased?|decreased?|reduced?)\b', 'clearance'),
    (r'\bAUC\s+(?:may\s+be\s+)?(?:increased?|decreased?)\b', 'auc'),
    (r'\bbioavailability\s+(?:may\s+be\s+)?(?:increased?|decreased?|reduced?)\b', 'bioavailability'),
    
    # General moderate keywords
    (r'\bmoderate\s+(?:risk|interaction|effect)\b', 'moderate'),
    (r'\bpossible\s+(?:interaction|effect|risk)\b', 'possible'),
    (r'\bpotential\s+(?:interaction|effect|risk|for)\b', 'potential'),
    (r'\bclinically\s+(?:significant|relevant|meaningful)\b', 'clinically_significant'),
    
    # CNS effects (not severe)
    (r'\bCNS\s+(?:depression|effects?)\b', 'cns_effects'),
    (r'\bsedation\b', 'sedation'),
    (r'\bdrowsiness\b', 'drowsiness'),
    (r'\bdizziness\b', 'dizziness'),
    
    # Bleeding risk (not severe)
    (r'\b(?:increased?\s+)?(?:risk\s+of\s+)?bleeding\b', 'bleeding_risk'),
    (r'\banticoagulant\s+effect\b', 'anticoagulant_effect'),
]


# Compile all patterns for efficiency
COMPILED_SEVERE = [(re.compile(p, re.IGNORECASE), name) for p, name in SEVERE_PATTERNS]
COMPILED_MINOR = [(re.compile(p, re.IGNORECASE), name) for p, name in MINOR_PATTERNS]
COMPILED_MODERATE = [(re.compile(p, re.IGNORECASE), name) for p, name in MODERATE_PATTERNS]


def classify_severity(description: str) -> Tuple[str, str]:
    """
    Classify interaction severity based on description text using regex patterns.
    
    Args:
        description: The interaction description text
        
    Returns:
        Tuple of (severity, matched_pattern_name)
        severity is one of: 'severe', 'moderate', 'minor', 'unknown'
    """
    if not description:
        return ('unknown', 'empty_description')
    
    # Check SEVERE patterns first (highest priority)
    for pattern, name in COMPILED_SEVERE:
        if pattern.search(description):
            return ('severe', name)
    
    # Check MINOR patterns next
    for pattern, name in COMPILED_MINOR:
        if pattern.search(description):
            return ('minor', name)
    
    # Check MODERATE patterns
    for pattern, name in COMPILED_MODERATE:
        if pattern.search(description):
            return ('moderate', name)
    
    # Default to moderate if no patterns matched
    return ('moderate', 'default')


def classify_severity_simple(description: str) -> str:
    """
    Simple version that just returns the severity string.
    """
    severity, _ = classify_severity(description)
    return severity


def get_all_matches(description: str) -> Dict[str, List[str]]:
    """
    Get all matched patterns for a description (useful for debugging).
    
    Returns:
        Dict with keys 'severe', 'moderate', 'minor' and list of matched pattern names
    """
    matches = {
        'severe': [],
        'moderate': [],
        'minor': []
    }
    
    if not description:
        return matches
    
    for pattern, name in COMPILED_SEVERE:
        if pattern.search(description):
            matches['severe'].append(name)
    
    for pattern, name in COMPILED_MINOR:
        if pattern.search(description):
            matches['minor'].append(name)
    
    for pattern, name in COMPILED_MODERATE:
        if pattern.search(description):
            matches['moderate'].append(name)
    
    return matches


def get_severity_color(severity: str) -> str:
    """
    Get the color code for a severity level.
    """
    colors = {
        'severe': '#ef4444',    # Red
        'moderate': '#f59e0b',  # Yellow/Amber
        'minor': '#22c55e',     # Green
        'unknown': '#6b7280'    # Gray
    }
    return colors.get(severity, colors['unknown'])


def get_severity_emoji(severity: str) -> str:
    """
    Get the emoji for a severity level.
    """
    emojis = {
        'severe': '🔴',
        'moderate': '🟡', 
        'minor': '🟢',
        'unknown': '⚪'
    }
    return emojis.get(severity, emojis['unknown'])


# Export pattern counts for documentation
PATTERN_COUNTS = {
    'severe': len(SEVERE_PATTERNS),
    'moderate': len(MODERATE_PATTERNS),
    'minor': len(MINOR_PATTERNS),
    'total': len(SEVERE_PATTERNS) + len(MODERATE_PATTERNS) + len(MINOR_PATTERNS)
}


if __name__ == "__main__":
    # Test the classifier
    test_descriptions = [
        "This combination is contraindicated due to risk of severe cardiac arrhythmia.",
        "May increase the serum concentration of the drug. Monitor closely.",
        "Minor interaction with minimal clinical significance.",
        "The risk of serotonin syndrome is increased when combined.",
        "Use with caution. Dose adjustment may be needed.",
        "Theoretical interaction, unlikely to be clinically significant.",
        "Can cause fatal respiratory depression.",
        "QT prolongation may occur.",
        "The metabolism of Drug A can be decreased by Drug B.",
    ]
    
    print("=" * 70)
    print("SEVERITY CLASSIFIER TEST")
    print("=" * 70)
    print(f"\nPatterns loaded: {PATTERN_COUNTS['total']} total")
    print(f"  - Severe:   {PATTERN_COUNTS['severe']} patterns")
    print(f"  - Moderate: {PATTERN_COUNTS['moderate']} patterns")
    print(f"  - Minor:    {PATTERN_COUNTS['minor']} patterns")
    print()
    
    for desc in test_descriptions:
        severity, pattern = classify_severity(desc)
        emoji = get_severity_emoji(severity)
        print(f"{emoji} [{severity.upper():8}] {pattern:20} | {desc[:60]}...")
