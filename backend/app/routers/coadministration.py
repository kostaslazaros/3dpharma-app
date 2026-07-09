"""Clinical co-administration ("συγχορήγηση") API routes."""
from fastapi import APIRouter, HTTPException

from ..models.coadministration import CoAdminRequest, CoAdminResult
from ..services.coadmin_service import check_coadministration
from ..services import condition_service as cs

router = APIRouter(prefix="/coadministration", tags=["coadministration"])


@router.get("/conditions")
async def list_conditions() -> dict:
    """List the supported patient conditions (for building the UI)."""
    return {
        "conditions": [
            {"key": key, "label": cfg["label"]}
            for key, cfg in cs.CONDITIONS.items()
        ]
    }


@router.post("/check")
async def coadministration_check(request: CoAdminRequest) -> CoAdminResult:
    """
    Check co-administration of one or more drugs against optional patient context
    (sex, age, conditions such as pregnancy / renal impairment / G6PD deficiency,
    and free-text diseases). Returns three buckets: contraindications, drug-drug
    interactions, and adverse effects — each severity-graded.
    """
    if not request.drugs:
        raise HTTPException(status_code=400, detail="At least one drug is required")
    if len(request.drugs) > 15:
        raise HTTPException(status_code=400, detail="Maximum 15 drugs allowed")

    result = check_coadministration(request.drugs, request.patient.model_dump())
    return CoAdminResult(**result)
