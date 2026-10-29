from fastapi import APIRouter, HTTPException, status
from app.schemas.threat import SearchRequest, SearchResponse, ThreatSignature
from app.core.redis_client import state_store
import logging

router = APIRouter(prefix="/registry", tags=["Global Threat Registry"])
logger = logging.getLogger(__name__)

@router.post("/search", response_model=SearchResponse)
async def search_threat_registry(payload: SearchRequest):
    # Queries the distributed Redis cache
    threat_data = await state_store.get_state(f"threat:{payload.signature_hash}")
    if threat_data:
        threat = ThreatSignature(**threat_data)
        return SearchResponse(is_threat=True, details=threat)
    return SearchResponse(is_threat=False)

@router.post("/report-zero-day", status_code=status.HTTP_201_CREATED)
async def report_new_threat(payload: ThreatSignature):
    existing = await state_store.get_state(f"threat:{payload.signature_hash}")
    if existing:
        raise HTTPException(status_code=400, detail="Threat already globally indexed.")
    
    # Broadcast to global distributed cache
    threat_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    await state_store.set_state(f"threat:{payload.signature_hash}", threat_dict)
    logger.warning(f"🚨 ZERO-DAY PROPAGATED GLOBALLY: {payload.signature_hash}")
    return {"status": "SUCCESS", "message": "Global Redis Registry Updated."}
