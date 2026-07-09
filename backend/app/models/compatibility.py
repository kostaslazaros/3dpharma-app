"""Compatibility check models"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel


class InteractionDetail(BaseModel):
    """Interaction detail model"""
    drug: str
    description: str
    severity: str = "moderate"
    source: Optional[str] = None


class RoutesInfo(BaseModel):
    """Routes of administration info"""
    drug1: List[str] = []
    drug2: List[str] = []
    common: List[str] = []


class DosingComparison(BaseModel):
    """Dosing comparison between drugs"""
    drug1: Dict[str, Optional[str]] = {}
    drug2: Dict[str, Optional[str]] = {}


class CompatibilityResult(BaseModel):
    """Full compatibility check result"""
    drug1: str
    drug2: str
    compatible: bool
    issues: List[str] = []
    warnings: List[str] = []
    recommendations: List[str] = []
    drug1_data: Optional[Dict[str, Any]] = None
    drug2_data: Optional[Dict[str, Any]] = None
    interactions: List[InteractionDetail] = []
    routes: RoutesInfo = RoutesInfo()
    dosing: DosingComparison = DosingComparison()


class MultiDrugCompatibilityResult(BaseModel):
    """Multi-drug compatibility result"""
    drugs: List[str]
    compatible: bool
    issues: List[str] = []
    warnings: List[str] = []
    recommendations: List[str] = []
    interactions: List[Dict[str, Any]] = []
    drug_details: List[Dict[str, Any]] = []
    common_routes: List[str] = []


class CompatibilityRequest(BaseModel):
    """Request model for compatibility check"""
    drug1: str
    drug2: str


class MultiDrugRequest(BaseModel):
    """Request model for multi-drug compatibility check"""
    drugs: List[str]


class ChatRequest(BaseModel):
    """Request model for AI chat"""
    message: str
    history: List[Dict[str, str]] = []


class ChatResponse(BaseModel):
    """Response model for AI chat"""
    response: str
    sources: List[str] = []
    drugs_mentioned: List[str] = []
