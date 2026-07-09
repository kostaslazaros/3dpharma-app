"""Drug API routes"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from ..services.drug_service import get_drug_service

router = APIRouter(prefix="/drugs", tags=["drugs"])


@router.get("/search")
async def search_drugs(
    q: str = Query(..., min_length=2, description="Search query (minimum 2 characters)")
) -> List[dict]:
    """
    Search for drugs by name.
    Returns a list of matching drug names and basic info.
    """
    service = get_drug_service()
    results = service.search_drugs(q)
    
    # Return enriched results
    enriched = []
    for name in results:
        drug = service.find_drug(name)
        if drug:
            categories = []
            for cat in drug.get('categories', []):
                cat_name = service._normalize_category_name(cat)
                if cat_name:
                    categories.append(cat_name)
            
            enriched.append({
                'name': name,
                'drugbank_id': drug.get('drugbank_ids', {}).get('primary'),
                'type': drug.get('type'),
                'categories': categories[:5]  # Limit categories
            })
    
    return enriched


@router.get("/info/{drug_name}")
async def get_drug_info(drug_name: str) -> dict:
    """
    Get detailed information about a specific drug.
    """
    service = get_drug_service()
    summary = service.get_summary(drug_name)
    
    if 'error' in summary:
        raise HTTPException(status_code=404, detail=summary['error'])
    
    return summary


@router.get("/categories")
async def get_all_categories() -> List[str]:
    """
    Get all available drug categories.
    """
    service = get_drug_service()
    return service.get_all_categories()


@router.get("/categories/{category}")
async def get_drugs_by_category(category: str) -> List[str]:
    """
    Get all drugs in a specific category.
    """
    service = get_drug_service()
    drugs = service.get_drugs_by_category(category)
    return drugs


@router.get("/alternatives/{drug_name}")
async def get_alternatives(drug_name: str) -> dict:
    """
    Get alternative drugs from the same category.
    """
    service = get_drug_service()
    
    drug = service.find_drug(drug_name)
    if not drug:
        raise HTTPException(status_code=404, detail=f"Drug '{drug_name}' not found")
    
    alternatives = service.get_alternatives_from_category(drug_name)
    
    return {
        'drug': drug_name,
        'alternatives': alternatives,
        'count': len(alternatives)
    }


@router.get("/database/info")
async def get_database_info() -> dict:
    """
    Get database metadata and statistics.
    """
    service = get_drug_service()
    return service.get_database_info()
