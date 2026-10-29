from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ThreatSignature(BaseModel):
    signature_hash: str = Field(
        ...,
        description="Acoustic fingerprint hash or SHA-256 signature of the voice sample",
    )
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        ...,
        description="Assigned threat severity rating",
    )
    reported_location: str = Field(
        ...,
        description="Geographic region or telecom circle of report origin",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of threat identification",
    )


class ThreatSearchRequest(BaseModel):
    signature_hash: str = Field(
        ...,
        min_length=6,
        description="Audio signature hash to lookup",
        example="c4134066830c4a3cde640795dbaab5775f70211c2eeed15d2abb26ad97d539c5",
    )


class ThreatSearchResponse(BaseModel):
    is_known_threat: bool
    threat_details: Optional[ThreatSignature] = None
    query_hash: str
    message: str

