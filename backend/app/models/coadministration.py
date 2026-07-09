"""Co-administration (clinical) check models."""
from typing import List, Optional
from pydantic import BaseModel, Field


class PatientContext(BaseModel):
    """Optional patient context for a co-administration check."""
    sex: Optional[str] = None            # "male" | "female" | None
    age: Optional[int] = None            # years
    conditions: List[str] = []           # e.g. ["pregnancy", "renal_impairment"]
    diseases: List[str] = []             # free-text diagnoses/symptoms


class CoAdminRequest(BaseModel):
    """Request for a clinical co-administration check."""
    drugs: List[str] = Field(default_factory=list)
    patient: PatientContext = Field(default_factory=PatientContext)


class CoAdminHit(BaseModel):
    """A single finding (contraindication, interaction, or adverse effect)."""
    drugs: List[str]
    condition: Optional[str] = None
    condition_label: Optional[str] = None
    description: str
    severity: str = "moderate"          # severe | moderate | minor | unknown
    emoji: Optional[str] = None
    source: Optional[str] = None
    category: str = "interaction"       # contraindication | interaction | adverse_effect


class CoAdminResult(BaseModel):
    """Full co-administration check result, galinos-style three buckets."""
    drugs: List[str]
    resolved_drugs: List[str] = []
    unresolved_drugs: List[str] = []
    patient: PatientContext
    contraindications: List[CoAdminHit] = []
    interactions: List[CoAdminHit] = []
    adverse_effects: List[CoAdminHit] = []
    summary: str = ""
    disclaimer: str = ""
