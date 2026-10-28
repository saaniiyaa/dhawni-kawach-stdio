from pydantic import BaseModel
from typing import Optional

class ThreatSignature(BaseModel):
    signature_hash: str
    risk_level: str
    reported_location: str = "Global"
    timestamp: float

class SearchRequest(BaseModel):
    signature_hash: str

class SearchResponse(BaseModel):
    is_threat: bool
    details: Optional[ThreatSignature] = None

