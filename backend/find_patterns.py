"""
Find patterns in drug interaction descriptions using regex
"""

import csv
import re
from collections import Counter, defaultdict

def find_patterns():
    print("Loading interactions...")
    
    descriptions = []
    with open("all_interactions_classified.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            descriptions.append(row['Description'])
    
    print(f"Loaded {len(descriptions):,} interactions")
    
    # Pattern categories to look for
    patterns = {
        # Action patterns - what happens
        'increase_effect': r'(?:may |can |will )?increase[sd]? (?:the )?(?:risk|effect|level|concentration|activity|toxicity|serum|plasma)',
        'decrease_effect': r'(?:may |can |will )?(?:decrease|reduce|lower)[sd]? (?:the )?(?:risk|effect|level|concentration|activity|efficacy)',
        'enhance': r'(?:may |can )?enhance[sd]? (?:the )?(?:effect|activity|action|toxicity)',
        'potentiate': r'(?:may |can )?potentiate[sd]?',
        'inhibit': r'(?:may |can )?inhibit[sd]?',
        'induce': r'(?:may |can )?induce[sd]?',
        
        # Risk patterns
        'risk_of': r'(?:risk|severity) of ([a-zA-Z\s]+?)(?:\.|,|and|can|may|when)',
        'increased_risk': r'increased? (?:the )?risk (?:of|for)',
        'adverse_effects': r'adverse (?:effects?|reactions?|events?)',
        
        # Severity indicators
        'contraindicated': r'contraindicated',
        'should_not': r'should not (?:be )?(?:used|combined|given|taken|administered)',
        'avoid': r'avoid(?:ed|ing)?',
        'caution': r'(?:use )?(?:with )?caution',
        'monitor': r'monitor(?:ed|ing)?',
        
        # Mechanism patterns
        'cyp_interaction': r'CYP[0-9A-Z]+',
        'metabolism': r'metaboli[sz](?:ed|m|ing)',
        'absorption': r'absorb(?:ed|tion|ing)',
        'excretion': r'excret(?:ed|ion|ing)',
        'clearance': r'clearance',
        'half_life': r'half[- ]?life',
        
        # Clinical outcomes
        'bleeding': r'bleed(?:ing)?|hemorrhag(?:e|ic|ing)',
        'hypotension': r'hypotens(?:ion|ive)',
        'hypertension': r'hypertens(?:ion|ive)',
        'arrhythmia': r'arrhythmi(?:a|as|c)',
        'qt_prolongation': r'QT[c]? (?:interval )?prolong(?:ation|ed|ing)',
        'serotonin_syndrome': r'serotonin syndrome',
        'cns_depression': r'CNS (?:depression|depressant)',
        'respiratory_depression': r'respiratory depression',
        'seizure': r'seizure[s]?|convulsion[s]?',
        'nephrotoxicity': r'nephrotoxic(?:ity)?|kidney (?:damage|toxicity|injury)',
        'hepatotoxicity': r'hepatotoxic(?:ity)?|liver (?:damage|toxicity|injury)',
        'cardiotoxicity': r'cardiotoxic(?:ity)?|cardiac (?:damage|toxicity)',
        
        # Pharmacokinetic terms
        'auc': r'\bAUC\b',
        'cmax': r'\bCmax\b',
        'bioavailability': r'bioavailability',
        
        # Common drug classes mentioned
        'anticoagulant': r'anticoagulant[s]?',
        'nsaid': r'NSAID[s]?|anti[- ]?inflammator',
        'opioid': r'opioid[s]?',
        'antidepressant': r'antidepressant[s]?',
        'antihypertensive': r'antihypertensive[s]?',
    }
    
    print(f"\n{'='*70}")
    print("PATTERN FREQUENCY ANALYSIS")
    print(f"{'='*70}")
    
    pattern_counts = {}
    pattern_examples = defaultdict(list)
    
    for name, pattern in patterns.items():
        regex = re.compile(pattern, re.IGNORECASE)
        count = 0
        for desc in descriptions:
            matches = regex.findall(desc)
            if matches:
                count += 1
                if len(pattern_examples[name]) < 3:
                    pattern_examples[name].append(desc[:150])
        pattern_counts[name] = count
    
    # Sort by count
    sorted_patterns = sorted(pattern_counts.items(), key=lambda x: -x[1])
    
    for name, count in sorted_patterns:
        pct = 100 * count / len(descriptions)
        print(f"\n  [{count:>8,}] ({pct:>5.1f}%) {name}")
        print(f"      Regex: {patterns[name]}")
    
    # Extract common phrase templates
    print(f"\n{'='*70}")
    print("COMMON SENTENCE TEMPLATES")
    print(f"{'='*70}")
    
    templates = [
        (r'^The (serum concentration|metabolism|therapeutic efficacy|risk or severity) of (.+?) can be (increased|decreased|reduced) when', 'Template: "The X of Y can be Z when..."'),
        (r'^(.+?) may (increase|decrease|enhance|reduce) the (.+?) of (.+?)\.?$', 'Template: "X may Y the Z of W"'),
        (r'^The risk or severity of (.+?) can be (increased|decreased)', 'Template: "Risk of X can be Y"'),
        (r'^(.+?) can cause a (decrease|increase|reduction)', 'Template: "X can cause a Y"'),
    ]
    
    for pattern, template_name in templates:
        regex = re.compile(pattern, re.IGNORECASE)
        count = sum(1 for d in descriptions if regex.search(d))
        pct = 100 * count / len(descriptions)
        print(f"\n  [{count:>8,}] ({pct:>5.1f}%) {template_name}")
        print(f"      Regex: {pattern[:80]}...")
    
    # Extract "risk of X" phrases
    print(f"\n{'='*70}")
    print("WHAT RISKS ARE MENTIONED (extracted from 'risk of X')")
    print(f"{'='*70}")
    
    risk_pattern = re.compile(r'risk (?:or severity )?of ([a-zA-Z][a-zA-Z\s,\-]+?)(?:\.|,| can| may| when| is)', re.IGNORECASE)
    risk_phrases = []
    for desc in descriptions:
        matches = risk_pattern.findall(desc)
        for m in matches:
            cleaned = m.strip().lower()
            if len(cleaned) > 3 and len(cleaned) < 50:
                risk_phrases.append(cleaned)
    
    risk_counts = Counter(risk_phrases)
    print("\n  Top 30 risks mentioned:")
    for risk, count in risk_counts.most_common(30):
        print(f"    [{count:>6,}] {risk}")
    
    # Extract action verbs
    print(f"\n{'='*70}")
    print("ACTION VERBS USED")
    print(f"{'='*70}")
    
    action_pattern = re.compile(r'\b(may|can|will|could|might) (increase|decrease|reduce|enhance|potentiate|inhibit|induce|cause|lead to|result in)\b', re.IGNORECASE)
    action_counts = Counter()
    for desc in descriptions:
        matches = action_pattern.findall(desc)
        for modal, verb in matches:
            action_counts[f"{modal.lower()} {verb.lower()}"] += 1
    
    print("\n  Top 20 action phrases:")
    for action, count in action_counts.most_common(20):
        print(f"    [{count:>7,}] {action}")
    
    # Classify by structure
    print(f"\n{'='*70}")
    print("DESCRIPTION STRUCTURE TYPES")
    print(f"{'='*70}")
    
    structures = {
        'starts_with_the': r'^The ',
        'starts_with_drug_may': r'^[A-Z][a-z]+ may ',
        'starts_with_drug_can': r'^[A-Z][a-z]+ can ',
        'contains_when_combined': r'when (?:it is )?combined with',
        'contains_co_administered': r'co[- ]?administered',
        'contains_concomitant': r'concomitant(?:ly)?',
    }
    
    for name, pattern in structures.items():
        regex = re.compile(pattern, re.IGNORECASE)
        count = sum(1 for d in descriptions if regex.search(d))
        pct = 100 * count / len(descriptions)
        print(f"  [{count:>8,}] ({pct:>5.1f}%) {name}")
    
    # Save detailed patterns to CSV
    print(f"\n{'='*70}")
    print("SAVING PATTERN ANALYSIS")
    print(f"{'='*70}")
    
    with open("interaction_patterns.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(['Pattern Name', 'Regex', 'Match Count', 'Percentage'])
        for name, count in sorted_patterns:
            pct = 100 * count / len(descriptions)
            writer.writerow([name, patterns[name], count, f"{pct:.2f}%"])
    print("  [OK] Pattern analysis saved to: interaction_patterns.csv")
    
    with open("risk_phrases.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(['Risk Phrase', 'Count'])
        for risk, count in risk_counts.most_common(100):
            writer.writerow([risk, count])
    print("  [OK] Risk phrases saved to: risk_phrases.csv")
    
    # Create improved severity regex
    print(f"\n{'='*70}")
    print("SUGGESTED IMPROVED SEVERITY REGEX")
    print(f"{'='*70}")
    
    print("""
SEVERE (Red) - Use these regex patterns:
  r'risk (?:or severity )?of (?:bleeding|hemorrhag|death|fatal)'
  r'(?:nephro|hepato|cardio)toxic'
  r'(?:serotonin syndrome|neuroleptic malignant)'
  r'(?:respiratory|CNS) depression'
  r'(?:cardiac|respiratory) arrest'
  r'(?:hyper|hypo)tens(?:ion|ive) (?:crisis|emergency)'
  r'\\bseizure|convulsion'
  r'\\barrhythmi'
  r'QT[c]? prolong'
  r'contraindicated'
  r'should not be (?:used|combined|given)'

MODERATE (Yellow):
  r'may (?:increase|decrease|enhance|reduce) the'
  r'(?:increased?|decreased?) (?:effect|level|concentration)'
  r'use (?:with )?caution'
  r'monitor(?:ed|ing)?'
  
MINOR (Green):
  r'(?:minor|mild|slight|minimal) (?:effect|interaction)'
  r'unlikely to be'
  r'theoretical'
""")

if __name__ == "__main__":
    find_patterns()
