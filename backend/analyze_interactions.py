"""
Analyze and classify drug interactions by severity using REGEX patterns

This script uses the same regex-based severity classifier as the live API
to ensure consistency between batch analysis and real-time classification.
"""

import json
import csv
import sys
import os
from collections import Counter

# Add the app directory to path so we can import the classifier
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.severity_classifier import (
    classify_severity_simple as classify_severity,
    classify_severity as classify_severity_with_pattern,
    get_severity_emoji,
    PATTERN_COUNTS,
    SEVERE_PATTERNS,
    MODERATE_PATTERNS,
    MINOR_PATTERNS
)

def analyze_interactions():
    print("=" * 60)
    print("DRUG INTERACTION SEVERITY ANALYZER (REGEX-BASED)")
    print("=" * 60)
    print(f"\nUsing {PATTERN_COUNTS['total']} regex patterns:")
    print(f"  - Severe:   {PATTERN_COUNTS['severe']} patterns")
    print(f"  - Moderate: {PATTERN_COUNTS['moderate']} patterns")
    print(f"  - Minor:    {PATTERN_COUNTS['minor']} patterns")
    
    print("\nLoading database...")
    with open("comprehensive_drug_database_compact.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    drugs = data.get("drugs", [])
    print(f"Loaded {len(drugs)} drugs")
    
    # Collect all interactions
    all_interactions = []
    interaction_texts = set()  # To avoid duplicates
    
    for drug in drugs:
        drug_name = drug.get('name', 'Unknown')
        interactions = drug.get('drug_interactions', [])
        
        for interaction in interactions:
            other_drug = interaction.get('name', 'Unknown')
            description = interaction.get('description', '')
            drugbank_id = interaction.get('drugbank_id', '')
            
            # Create unique key to avoid duplicates
            key = f"{min(drug_name, other_drug)}|{max(drug_name, other_drug)}|{description[:100]}"
            
            if key not in interaction_texts:
                interaction_texts.add(key)
                
                # Get severity AND the pattern that matched
                severity, pattern_name = classify_severity_with_pattern(description)
                
                all_interactions.append({
                    'drug1': drug_name,
                    'drug2': other_drug,
                    'drugbank_id': drugbank_id,
                    'description': description,
                    'severity': severity,
                    'pattern': pattern_name,
                    'description_length': len(description)
                })
    
    print(f"\nTotal unique interactions: {len(all_interactions)}")
    
    # Count by severity
    severity_counts = Counter(i['severity'] for i in all_interactions)
    
    print(f"\n{'='*60}")
    print("INTERACTION SEVERITY DISTRIBUTION")
    print(f"{'='*60}")
    for severity, count in severity_counts.most_common():
        pct = 100 * count / len(all_interactions)
        marker = "[!!!]" if severity == 'severe' else "[!!]" if severity == 'moderate' else "[!]" if severity == 'minor' else "[?]"
        print(f"  {marker} {severity.upper()}: {count:,} ({pct:.1f}%)")
    
    # Sort interactions by severity (severe first)
    severity_order = {'severe': 0, 'moderate': 1, 'minor': 2, 'unknown': 3}
    all_interactions.sort(key=lambda x: (severity_order.get(x['severity'], 99), x['drug1']))
    
    # Export ALL interactions to CSV (with pattern info)
    csv_file = "all_interactions_classified.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(['Drug 1', 'Drug 2', 'DrugBank ID', 'Severity', 'Pattern', 'Description'])
        for i in all_interactions:
            emoji = get_severity_emoji(i['severity'])
            writer.writerow([i['drug1'], i['drug2'], i['drugbank_id'], f"{emoji} {i['severity']}", i['pattern'], i['description']])
    print(f"\n[OK] All interactions exported to: {csv_file}")
    
    # Export SEVERE interactions only
    severe_file = "severe_interactions.csv"
    severe = [i for i in all_interactions if i['severity'] == 'severe']
    with open(severe_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(['Drug 1', 'Drug 2', 'DrugBank ID', 'Pattern', 'Description'])
        for i in severe:
            writer.writerow([i['drug1'], i['drug2'], i['drugbank_id'], i['pattern'], i['description']])
    print(f"[OK] Severe interactions exported to: {severe_file} ({len(severe):,} interactions)")
    
    # Export MINOR interactions only (new!)
    minor_file = "minor_interactions.csv"
    minor = [i for i in all_interactions if i['severity'] == 'minor']
    with open(minor_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(['Drug 1', 'Drug 2', 'DrugBank ID', 'Pattern', 'Description'])
        for i in minor:
            writer.writerow([i['drug1'], i['drug2'], i['drugbank_id'], i['pattern'], i['description']])
    print(f"[OK] Minor interactions exported to: {minor_file} ({len(minor):,} interactions)")
    
    # Show sample of severe interactions
    print(f"\n{'='*60}")
    print("SAMPLE SEVERE INTERACTIONS (first 30)")
    print(f"{'='*60}")
    for i, interaction in enumerate(severe[:30], 1):
        desc_short = interaction['description'][:100] + "..." if len(interaction['description']) > 100 else interaction['description']
        print(f"\n{i}. [SEVERE] {interaction['drug1']} + {interaction['drug2']}")
        print(f"   {desc_short}")
    
    # Find the regex patterns that triggered severe classification
    print(f"\n{'='*60}")
    print("SEVERE PATTERN TRIGGERS (what makes an interaction severe)")
    print(f"{'='*60}")
    pattern_counts = Counter()
    for interaction in severe:
        severity, pattern_name = classify_severity_with_pattern(interaction['description'])
        if pattern_name:
            pattern_counts[pattern_name] += 1
    
    for pattern, count in pattern_counts.most_common(20):
        print(f"  '{pattern}': {count} times")
    
    # Create a JSON file with severity classification for the UI
    severity_lookup = {}
    for interaction in all_interactions:
        key = f"{interaction['drug1'].lower()}|{interaction['drug2'].lower()}"
        key_reverse = f"{interaction['drug2'].lower()}|{interaction['drug1'].lower()}"
        severity_lookup[key] = interaction['severity']
        severity_lookup[key_reverse] = interaction['severity']
    
    # Save as JSON for easy UI lookup
    with open("interaction_severities.json", "w", encoding="utf-8") as f:
        json.dump({
            'total_interactions': len(all_interactions),
            'severe_count': severity_counts.get('severe', 0),
            'moderate_count': severity_counts.get('moderate', 0),
            'minor_count': severity_counts.get('minor', 0),
            'pattern_counts': PATTERN_COUNTS,
            'patterns': {
                'severe': [name for _, name in SEVERE_PATTERNS],
                'moderate': [name for _, name in MODERATE_PATTERNS],
                'minor': [name for _, name in MINOR_PATTERNS]
            }
        }, f, indent=2)
    print(f"\n[OK] Severity metadata saved to: interaction_severities.json")
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Total unique interactions: {len(all_interactions):,}")
    print(f"  [!!!] SEVERE:   {severity_counts.get('severe', 0):,}")
    print(f"  [!!]  MODERATE: {severity_counts.get('moderate', 0):,}")
    print(f"  [!]   MINOR:    {severity_counts.get('minor', 0):,}")
    print(f"  [?]   UNKNOWN:  {severity_counts.get('unknown', 0):,}")
    print(f"\nFiles created:")
    print(f"  - all_interactions_classified.csv (all interactions)")
    print(f"  - severe_interactions.csv (severe only)")
    print(f"  - interaction_severities.json (metadata for UI)")

if __name__ == "__main__":
    analyze_interactions()
