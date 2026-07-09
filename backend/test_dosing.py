"""Test dosing extraction"""
from app.services.drug_service import DrugService

# Reset singleton
DrugService._initialized = False
DrugService._instance = None

service = DrugService()

# Test several drugs
test_drugs = ['Lisinopril', 'Metformin', 'Aspirin', 'Ibuprofen', 'Amoxicillin']

for drug_name in test_drugs:
    summary = service.get_summary(drug_name)
    if 'error' in summary:
        print(f"{drug_name}: NOT FOUND")
        continue
    
    dosing = summary.get('dosing', {})
    print(f"\n{drug_name}:")
    print(f"  frequency:    {dosing.get('frequency') or 'N/A'}")
    print(f"  times/day:    {dosing.get('times_per_day') or 'N/A'}")
    print(f"  routes:       {dosing.get('routes') or 'N/A'}")
    print(f"  strengths:    {dosing.get('strengths') or 'N/A'}")
