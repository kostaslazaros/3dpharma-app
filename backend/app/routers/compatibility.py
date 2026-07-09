"""Compatibility check API routes"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models.compatibility import CompatibilityRequest, MultiDrugRequest
from ..services.drug_service import get_drug_service

router = APIRouter(prefix="/compatibility", tags=["compatibility"])


class AlternativesRequest(BaseModel):
    """Request for finding compatible alternatives"""
    target_drug: str
    category: str
    limit: Optional[int] = 10


@router.post("/check")
async def check_compatibility(request: CompatibilityRequest) -> dict:
    """
    Check compatibility between two drugs for 3D printing.
    """
    service = get_drug_service()
    result = service.check_compatibility(request.drug1, request.drug2)
    return result


@router.post("/check-multi")
async def check_multi_drug_compatibility(request: MultiDrugRequest) -> dict:
    """
    Check compatibility between multiple drugs (3+) for 3D printing.
    """
    if len(request.drugs) < 2:
        raise HTTPException(status_code=400, detail="At least 2 drugs required")
    
    if len(request.drugs) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 drugs allowed")
    
    service = get_drug_service()
    
    result = {
        'drugs': request.drugs,
        'compatible': True,
        'issues': [],
        'warnings': [],
        'recommendations': [],
        'interactions': [],
        'no_interaction_pairs': [],
        'drug_details': [],
        'common_routes': []
    }
    
    # Get details for each drug
    all_routes = []
    for drug_name in request.drugs:
        summary = service.get_summary(drug_name)
        if 'error' in summary:
            result['issues'].append(f"Drug '{drug_name}' not found in database")
            result['compatible'] = False
            continue
        
        routes = summary.get('dosing', {}).get('routes', [])
        all_routes.append(set(r.lower() for r in routes))
        
        result['drug_details'].append({
            'name': drug_name,
            'type': summary.get('type'),
            'routes': routes,
            'frequency': summary.get('dosing', {}).get('frequency'),
            'times_per_day': summary.get('dosing', {}).get('times_per_day')
        })
        
        # Check if biologic
        if summary.get('type') == 'biotech':
            result['issues'].append(f"{drug_name} is a biologic - cannot be 3D printed with standard methods")
            result['compatible'] = False
    
    # Find common routes
    if all_routes:
        common = all_routes[0]
        for routes_set in all_routes[1:]:
            common = common & routes_set
        result['common_routes'] = list(common)
    
    # Check pairwise interactions
    drugs_list = request.drugs
    for i in range(len(drugs_list)):
        for j in range(i + 1, len(drugs_list)):
            drug1_name = drugs_list[i]
            drug2_name = drugs_list[j]
            
            compatibility = service.check_compatibility(drug1_name, drug2_name)
            pair_interactions = compatibility.get('interactions', [])
            
            if not pair_interactions:
                result['no_interaction_pairs'].append([drug1_name, drug2_name])
                continue
            
            for interaction in pair_interactions:
                result['interactions'].append({
                    'drug1': drug1_name,
                    'drug2': drug2_name,
                    'interaction': interaction
                })
                
                if interaction.get('severity') == 'severe':
                    result['issues'].append(
                        f"❌ SEVERE INTERACTION between {drug1_name} & {drug2_name}: {interaction.get('description', '')}"
                    )
                    result['compatible'] = False
                else:
                    result['warnings'].append(
                        f"⚠️ {drug1_name} ↔ {drug2_name}: {interaction.get('description', '')}"
                    )
    
    # Add recommendations
    if result['compatible']:
        types = list(set(d.get('type', 'unknown') for d in result['drug_details']))
        result['recommendations'].append(f"📊 Drug types: {', '.join(str(t) for t in types)}")
        
        if result['common_routes']:
            result['recommendations'].append(f"🛣️ Common routes of administration: {', '.join(result['common_routes'])}")
    
    # Check dosing frequency compatibility
    frequencies = set()
    for detail in result['drug_details']:
        if detail.get('times_per_day'):
            frequencies.add(detail['times_per_day'])
    
    if len(frequencies) > 1:
        freq_list = ', '.join(
            f"{d['name']}: {d.get('frequency', 'N/A')}" 
            for d in result['drug_details'] 
            if d.get('frequency')
        )
        if freq_list:
            result['warnings'].append(f"⚠️ Different dosing frequencies detected: {freq_list}")
            result['recommendations'].append('📊 Timed-release formulation or separate administration may be needed')
    elif len(frequencies) == 1:
        freq = next((d.get('frequency') for d in result['drug_details'] if d.get('frequency')), None)
        if freq:
            result['recommendations'].append(f"📊 All drugs have compatible dosing frequency: {freq}")
    
    return result


@router.post("/find-alternatives")
async def find_compatible_alternatives(request: AlternativesRequest) -> dict:
    """
    Find drugs from a specific category that have NO interactions with the target drug.
    Useful for suggesting alternatives when two drugs have interactions.
    """
    service = get_drug_service()
    
    # Find the target drug first
    target = service.find_drug(request.target_drug)
    if not target:
        raise HTTPException(status_code=404, detail=f"Target drug '{request.target_drug}' not found")
    
    # Get compatible alternatives
    alternatives = service.find_compatible_alternatives(
        request.target_drug, 
        request.category, 
        request.limit or 10
    )
    
    return {
        'target_drug': request.target_drug,
        'category': request.category,
        'alternatives': alternatives,
        'count': len(alternatives)
    }
