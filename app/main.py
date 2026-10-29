import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1.endpoints import agent_builder, shield_monitor, threat_registry

app = FastAPI(title="Dhwani-Kavach Studio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# In-memory sliding window rate limiter (Max 100 requests per second per IP)
IP_RATE_LIMIT = {}
MAX_REQS_PER_SEC = 100

@app.middleware("http")
async def ddos_protection_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    current_time = int(time.time())
    
    if client_ip not in IP_RATE_LIMIT:
        IP_RATE_LIMIT[client_ip] = {"time": current_time, "count": 1}
    else:
        if IP_RATE_LIMIT[client_ip]["time"] == current_time:
            IP_RATE_LIMIT[client_ip]["count"] += 1
            if IP_RATE_LIMIT[client_ip]["count"] > MAX_REQS_PER_SEC:
                return JSONResponse(
                    status_code=429, 
                    content={"detail": "DDoS Protection Triggered. Traffic dropped."}
                )
        else:
            IP_RATE_LIMIT[client_ip] = {"time": current_time, "count": 1}
            
    response = await call_next(request)
    return response

# Core API and WebSocket Routers
app.include_router(agent_builder.router, prefix="/api/v1")
app.include_router(shield_monitor.router, prefix="/ws/v1")
app.include_router(shield_monitor.router, prefix="/api/v1")
app.include_router(threat_registry.router, prefix="/api/v1")

app.mount("/", StaticFiles(directory="static", html=True), name="static")

@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "service": "dhwani-kavach-studio"}
