"""Drug data models for API responses"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel


class DrugInteraction(BaseModel):
    """Drug interaction model"""
    drugbank_id: Optional[str] = None
    name: str
    description: str
    severity: str = "moderate"


class DosingInfo(BaseModel):
    """Dosing information model"""
    has_dosing: bool = False
    source: Optional[str] = None
    frequency: Optional[str] = None
    times_per_day: Optional[str] = None
    routes: List[str] = []


class PhysicalProperties(BaseModel):
    """Physical properties model"""
    melting_point: Optional[str] = None
    water_solubility: Optional[str] = None
    molecular_weight: Optional[str] = None
    logP: Optional[str] = None
    pKa: Optional[str] = None


class Pharmacokinetics(BaseModel):
    """Pharmacokinetics model"""
    half_life: Optional[str] = None
    absorption: Optional[str] = None
    metabolism: Optional[str] = None


class DosageForm(BaseModel):
    """Dosage form model"""
    form: Optional[str] = None
    route: Optional[str] = None
    strength: Optional[str] = None


class DrugSummary(BaseModel):
    """Complete drug summary model"""
    name: str
    drugbank_id: Optional[str] = None
    type: Optional[str] = None
    groups: List[str] = []
    description: str = ""
    dosing: DosingInfo
    interaction_count: int = 0
    food_interactions: List[str] = []
    interactions_list: List[Dict[str, Any]] = []
    properties: Dict[str, str] = {}
    pharmacokinetics: Pharmacokinetics
    dosages: List[DosageForm] = []
    categories: List[str] = []


class DrugSearchResult(BaseModel):
    """Drug search result model"""
    name: str
    drugbank_id: Optional[str] = None
    type: Optional[str] = None
    categories: List[str] = []


class DatabaseInfo(BaseModel):
    """Database metadata model"""
    total_drugs: int
    drugs_with_dosing: int
    source: str
