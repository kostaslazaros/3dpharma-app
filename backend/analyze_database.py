"""
Analyze the comprehensive drug database and generate reports
"""

import json
import csv
from collections import Counter, defaultdict
from pathlib import Path

def analyze_database():
    print("Loading database...")
    with open("comprehensive_drug_database_compact.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    drugs = data.get("drugs", [])
    print(f"\n{'='*60}")
    print(f"DRUG DATABASE ANALYSIS")
    print(f"{'='*60}")
    print(f"\nTotal drugs: {len(drugs)}")
    
    # Analyze structure - get all unique keys
    all_keys = set()
    nested_keys = defaultdict(set)
    
    for drug in drugs:
        all_keys.update(drug.keys())
        for key, value in drug.items():
            if isinstance(value, dict):
                nested_keys[key].update(value.keys())
    
    print(f"\n{'='*60}")
    print("TOP-LEVEL COLUMNS/FIELDS:")
    print(f"{'='*60}")
    for key in sorted(all_keys):
        print(f"  - {key}")
    
    print(f"\n{'='*60}")
    print("NESTED FIELDS:")
    print(f"{'='*60}")
    for parent, children in sorted(nested_keys.items()):
        print(f"\n  {parent}:")
        for child in sorted(children):
            print(f"    - {child}")
    
    # Analyze dosing information (correct field: dosing_info)
    print(f"\n{'='*60}")
    print("DOSING ANALYSIS:")
    print(f"{'='*60}")
    
    has_dosing = 0
    no_dosing = 0
    has_frequency = 0
    no_frequency = 0
    has_times_per_day = 0
    no_times_per_day = 0
    has_routes = 0
    no_routes = 0
    
    drugs_without_frequency = []
    drugs_with_frequency = []
    frequency_values = Counter()
    times_per_day_values = Counter()
    route_values = Counter()
    
    for drug in drugs:
        dosing = drug.get("dosing_info", {})  # Correct field name
        
        has_dosing_flag = dosing.get("has_dosing", False)
        if has_dosing_flag:
            has_dosing += 1
        else:
            no_dosing += 1
        
        freq = dosing.get("frequency")
        if freq and str(freq).strip():
            has_frequency += 1
            frequency_values[str(freq)] += 1
            drugs_with_frequency.append({
                "name": drug.get("name", "Unknown"),
                "frequency": freq,
                "times_per_day": dosing.get("times_per_day"),
                "routes": dosing.get("routes", [])
            })
        else:
            no_frequency += 1
            drugs_without_frequency.append(drug.get("name", "Unknown"))
        
        tpd = dosing.get("times_per_day")
        if tpd:
            has_times_per_day += 1
            times_per_day_values[str(tpd)] += 1
        else:
            no_times_per_day += 1
        
        routes = dosing.get("routes", [])
        if routes:
            has_routes += 1
            for r in routes:
                route_values[r] += 1
        else:
            no_routes += 1
    
    print(f"\n  has_dosing flag = True:  {has_dosing:,} ({100*has_dosing/len(drugs):.1f}%)")
    print(f"  has_dosing flag = False: {no_dosing:,} ({100*no_dosing/len(drugs):.1f}%)")
    print(f"\n  Frequency defined:       {has_frequency:,} ({100*has_frequency/len(drugs):.1f}%)")
    print(f"  Frequency NOT defined:   {no_frequency:,} ({100*no_frequency/len(drugs):.1f}%)")
    print(f"\n  Times/day defined:       {has_times_per_day:,} ({100*has_times_per_day/len(drugs):.1f}%)")
    print(f"  Times/day NOT defined:   {no_times_per_day:,} ({100*no_times_per_day/len(drugs):.1f}%)")
    print(f"\n  Routes defined:          {has_routes:,} ({100*has_routes/len(drugs):.1f}%)")
    print(f"  Routes NOT defined:      {no_routes:,} ({100*no_routes/len(drugs):.1f}%)")
    
    if frequency_values:
        print(f"\n  Top Frequency Values:")
        for val, count in frequency_values.most_common(10):
            print(f"    '{val}': {count:,}")
    
    if times_per_day_values:
        print(f"\n  Times Per Day Values:")
        for val, count in times_per_day_values.most_common(10):
            print(f"    '{val}': {count:,}")
    
    if route_values:
        print(f"\n  Top Routes:")
        for val, count in route_values.most_common(15):
            print(f"    '{val}': {count:,}")
    
    # Analyze drug types
    print(f"\n{'='*60}")
    print("DRUG TYPES:")
    print(f"{'='*60}")
    type_counts = Counter(drug.get("type", "Unknown") for drug in drugs)
    for drug_type, count in type_counts.most_common(20):
        print(f"  {drug_type or 'None'}: {count:,}")
    
    # Analyze groups
    print(f"\n{'='*60}")
    print("DRUG GROUPS:")
    print(f"{'='*60}")
    all_groups = []
    for drug in drugs:
        all_groups.extend(drug.get("groups", []))
    group_counts = Counter(all_groups)
    for grp, count in group_counts.most_common():
        print(f"  {grp}: {count:,}")
    
    # Analyze categories
    print(f"\n{'='*60}")
    print("TOP 20 CATEGORIES:")
    print(f"{'='*60}")
    all_categories = []
    for drug in drugs:
        all_categories.extend(drug.get("categories", []))
    category_counts = Counter(all_categories)
    print(f"  Total unique categories: {len(category_counts):,}")
    for cat, count in category_counts.most_common(20):
        print(f"  {cat}: {count:,}")
    
    # Analyze interactions (correct field: drug_interactions)
    print(f"\n{'='*60}")
    print("INTERACTIONS ANALYSIS:")
    print(f"{'='*60}")
    interaction_counts = [len(drug.get("drug_interactions", [])) for drug in drugs]
    drugs_with_interactions = sum(1 for c in interaction_counts if c > 0)
    total_interactions = sum(interaction_counts)
    max_interactions = max(interaction_counts) if interaction_counts else 0
    
    print(f"  Drugs with interactions: {drugs_with_interactions:,} ({100*drugs_with_interactions/len(drugs):.1f}%)")
    print(f"  Total interactions:      {total_interactions:,}")
    print(f"  Max interactions:        {max_interactions}")
    print(f"  Avg interactions:        {total_interactions/len(drugs):.1f}" if drugs else "  Avg: N/A")
    
    # Food interactions
    food_interaction_counts = [len(drug.get("food_interactions", [])) for drug in drugs]
    drugs_with_food = sum(1 for c in food_interaction_counts if c > 0)
    total_food = sum(food_interaction_counts)
    print(f"\n  Drugs with food interactions: {drugs_with_food:,}")
    print(f"  Total food interactions:      {total_food:,}")
    
    # Description and other text fields
    print(f"\n{'='*60}")
    print("TEXT FIELDS COVERAGE:")
    print(f"{'='*60}")
    has_desc = sum(1 for d in drugs if d.get("description"))
    has_moa = sum(1 for d in drugs if d.get("mechanism_of_action"))
    has_absorption = sum(1 for d in drugs if d.get("absorption"))
    has_metabolism = sum(1 for d in drugs if d.get("metabolism"))
    has_half_life = sum(1 for d in drugs if d.get("half_life"))
    
    print(f"  Description:         {has_desc:,} ({100*has_desc/len(drugs):.1f}%)")
    print(f"  Mechanism of Action: {has_moa:,} ({100*has_moa/len(drugs):.1f}%)")
    print(f"  Absorption:          {has_absorption:,} ({100*has_absorption/len(drugs):.1f}%)")
    print(f"  Metabolism:          {has_metabolism:,} ({100*has_metabolism/len(drugs):.1f}%)")
    print(f"  Half Life:           {has_half_life:,} ({100*has_half_life/len(drugs):.1f}%)")
    
    # Export to CSV
    print(f"\n{'='*60}")
    print("EXPORTING TO CSV...")
    print(f"{'='*60}")
    
    csv_file = "drug_database_full.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            "Name",
            "DrugBank ID (Primary)",
            "Type",
            "Groups",
            "Categories",
            "has_dosing",
            "Frequency",
            "Times Per Day",
            "Routes",
            "Dosing Source",
            "Interaction Count",
            "Food Interaction Count",
            "Has Description",
            "Has Mechanism",
            "Has Absorption",
            "Has Metabolism",
            "Has Half Life"
        ])
        
        # Data
        for drug in drugs:
            dosing = drug.get("dosing_info", {})
            drugbank = drug.get("drugbank_ids", {})
            writer.writerow([
                drug.get("name", ""),
                drugbank.get("primary", ""),
                drug.get("type", ""),
                "; ".join(drug.get("groups", [])),
                "; ".join(drug.get("categories", [])[:5]),  # Limit categories
                "Yes" if dosing.get("has_dosing") else "No",
                dosing.get("frequency", ""),
                dosing.get("times_per_day", ""),
                "; ".join(dosing.get("routes", [])),
                dosing.get("source", ""),
                len(drug.get("drug_interactions", [])),
                len(drug.get("food_interactions", [])),
                "Yes" if drug.get("description") else "No",
                "Yes" if drug.get("mechanism_of_action") else "No",
                "Yes" if drug.get("absorption") else "No",
                "Yes" if drug.get("metabolism") else "No",
                "Yes" if drug.get("half_life") else "No"
            ])
    
    print(f"  Full database exported to: {csv_file}")
    
    # Export drugs WITH frequency (the valuable ones)
    with_freq_file = "drugs_with_dosing.csv"
    with open(with_freq_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Drug Name", "Frequency", "Times Per Day", "Routes"])
        for d in drugs_with_frequency:
            writer.writerow([
                d["name"],
                d["frequency"],
                d["times_per_day"] or "",
                "; ".join(d["routes"]) if d["routes"] else ""
            ])
    
    print(f"  Drugs WITH dosing exported to: {with_freq_file} ({len(drugs_with_frequency):,} drugs)")
    
    # Export drugs without frequency
    no_freq_file = "drugs_without_dosing.csv"
    with open(no_freq_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Drug Name"])
        for name in drugs_without_frequency:
            writer.writerow([name])
    
    print(f"  Drugs WITHOUT dosing exported to: {no_freq_file} ({len(drugs_without_frequency):,} drugs)")
    
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    print(f"  Total drugs:           {len(drugs):,}")
    print(f"  With dosing info:      {has_frequency:,} ({100*has_frequency/len(drugs):.1f}%)")
    print(f"  Without dosing info:   {no_frequency:,} ({100*no_frequency/len(drugs):.1f}%)")
    print(f"  With interactions:     {drugs_with_interactions:,}")
    print(f"  Unique categories:     {len(category_counts):,}")
    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE!")
    print(f"{'='*60}")

if __name__ == "__main__":
    analyze_database()
