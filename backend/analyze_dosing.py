"""Analyze where dosing data can be extracted from"""
import json

with open('comprehensive_drug_database_compact.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

drugs = data.get('drugs', [])

print(f"Total drugs: {len(drugs)}")

# Count dosing availability
has_dosing = 0
has_frequency = 0
has_routes = 0
has_instructions = 0
has_openfda_full = 0

# Sample drugs with missing frequency but has data elsewhere
samples_with_instructions = []
samples_with_openfda = []

for drug in drugs:
    dosing = drug.get('dosing_info', {})
    
    if dosing.get('has_dosing'):
        has_dosing += 1
    if dosing.get('frequency'):
        has_frequency += 1
    if dosing.get('routes'):
        has_routes += 1
    if dosing.get('instructions'):
        has_instructions += 1
    if dosing.get('openfda_full'):
        has_openfda_full += 1
    
    # Find samples where frequency is missing but instructions exist
    if not dosing.get('frequency') and dosing.get('instructions'):
        if len(samples_with_instructions) < 3:
            samples_with_instructions.append({
                'name': drug.get('name'),
                'instructions': dosing.get('instructions')[:300]
            })
    
    # Find samples with openfda_full data
    if not dosing.get('frequency') and dosing.get('openfda_full'):
        if len(samples_with_openfda) < 3:
            samples_with_openfda.append({
                'name': drug.get('name'),
                'openfda_full': dosing.get('openfda_full')
            })

print(f"""
DOSING DATA AVAILABILITY
========================
has_dosing=True:     {has_dosing:,} drugs
has frequency:       {has_frequency:,} drugs  
has routes:          {has_routes:,} drugs
has instructions:    {has_instructions:,} drugs
has openfda_full:    {has_openfda_full:,} drugs

MISSING frequency but HAS instructions: {has_instructions - has_frequency if has_instructions > has_frequency else 'N/A'}
""")

print("=" * 60)
print("SAMPLES: Drugs with INSTRUCTIONS but no FREQUENCY")
print("=" * 60)
for s in samples_with_instructions:
    print(f"\n{s['name']}:")
    print(f"  Instructions: {s['instructions']}...")

print("\n" + "=" * 60)
print("SAMPLES: Drugs with OPENFDA_FULL data")
print("=" * 60)
for s in samples_with_openfda:
    print(f"\n{s['name']}:")
    print(f"  openfda_full keys: {list(s['openfda_full'].keys())}")
    print(f"  route: {s['openfda_full'].get('route')}")
    print(f"  instructions: {str(s['openfda_full'].get('instructions', ''))[:200]}...")

# Check what other top-level keys might contain dosing info
print("\n" + "=" * 60)
print("ALL TOP-LEVEL KEYS IN DRUG RECORDS")
print("=" * 60)
all_keys = set()
for drug in drugs[:100]:
    all_keys.update(drug.keys())
print(sorted(all_keys))

# Check the 'dosages' key
print("\n" + "=" * 60)
print("CHECKING 'dosages' KEY")
print("=" * 60)
has_dosages = 0
dosages_samples = []
for drug in drugs:
    if drug.get('dosages'):
        has_dosages += 1
        if len(dosages_samples) < 5:
            dosages_samples.append({
                'name': drug.get('name'),
                'dosages': drug.get('dosages')
            })

print(f"Drugs with 'dosages' key: {has_dosages}")
for s in dosages_samples:
    print(f"\n{s['name']}:")
    dosages_data = s['dosages']
    if isinstance(dosages_data, list):
        for d in dosages_data[:3]:
            print(f"  - {d}")
    else:
        print(f"  {str(dosages_data)[:200]}")

# Check for frequency patterns in instructions
print("\n" + "=" * 60)
print("FREQUENCY PATTERNS FOUND IN INSTRUCTIONS")
print("=" * 60)
import re
patterns = {
    'once daily': re.compile(r'\b(?:once[\s-]+(?:a\s+)?day|once[\s-]+daily|q\.?d\.?|qd|daily)\b', re.I),
    'twice daily': re.compile(r'\b(?:twice[\s-]+(?:a\s+)?day|twice[\s-]+daily|b\.?i\.?d\.?|bid)\b', re.I),
    'three times daily': re.compile(r'\b(?:three\s+times[\s-]+(?:a\s+)?day|t\.?i\.?d\.?|tid)\b', re.I),
    'weekly': re.compile(r'\b(?:once[\s-]+(?:a\s+)?week|weekly|every\s+week)\b', re.I),
    'every X hours': re.compile(r'\b(?:every\s+\d+\s*(?:hours?|hrs?)|q\d+h)\b', re.I),
}

pattern_counts = {k: 0 for k in patterns}
for drug in drugs:
    dosing = drug.get('dosing_info', {})
    instructions = dosing.get('instructions', '') or ''
    openfda_instr = dosing.get('openfda_full', {}).get('instructions', '') or ''
    combined = instructions + ' ' + openfda_instr
    
    for name, pattern in patterns.items():
        if pattern.search(combined):
            pattern_counts[name] += 1

for name, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
    print(f"  {name}: {count} drugs")
