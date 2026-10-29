from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-Enterprise-Key", auto_error=False)

# Simulated Global Enterprise Clients
AUTHORIZED_TENANTS = {
    "live_sk_hdfc_9982": {"name": "HDFC Bank", "tier": "enterprise", "webhooks_enabled": True},
    "live_sk_airtel_441x": {"name": "Airtel Telecom", "tier": "infrastructure", "webhooks_enabled": True}
}

async def verify_enterprise_tenant(api_key_header: str = Security(API_KEY_HEADER)):
    if not api_key_header or api_key_header not in AUTHORIZED_TENANTS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Enterprise API Key",
        )
    return AUTHORIZED_TENANTS[api_key_header]

