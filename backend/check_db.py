import json

with open('comprehensive_drug_database_compact.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

drugs = data.get('drugs', [])
print(f"Total drugs: {len(drugs)}")
print("\nSample drugs:")
for d in drugs[:15]:
    print(f"  - {d.get('name')}")
