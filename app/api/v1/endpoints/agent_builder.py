import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from elevenlabs.client import ElevenLabs
from app.core.config import settings

router = APIRouter(prefix="/agents", tags=["Agent Builder"])
logger = logging.getLogger(__name__)

class AgentDeployRequest(BaseModel):
    agent_name: str = Field(default="Dhwani Secure Voice Agent")
    agent_prompt: str = Field(...)
    first_message: str = Field(default="Hello! I am your secure voice assistant.")
    voice_id: str = Field(default="21m00Tcm4TlvDq8ikWAM")
    language: str = Field(default="en")

class AgentDeployResponse(BaseModel):
    agent_id: str
    name: str
    status: str
    embed_url: str | None = None
    message: str

@router.post("/deploy", response_model=AgentDeployResponse, status_code=status.HTTP_201_CREATED)
async def deploy_conversational_agent(payload: AgentDeployRequest):
    if not settings.ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY missing.")
    try:
        client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
        conversation_config = {
            "agent": {
                "prompt": {"prompt": payload.agent_prompt},
                "first_message": payload.first_message,
                "language": payload.language,
            },
            "tts": {"voice_id": payload.voice_id, "model_id": "eleven_flash_v2_5"},
        }
        response = client.conversational_ai.create_agent(name=payload.agent_name, conversation_config=conversation_config)
        agent_id = response.agent_id if hasattr(response, "agent_id") else response.get("agent_id")
        return AgentDeployResponse(
            agent_id=agent_id, name=payload.agent_name, status="ACTIVE",
            embed_url=f"https://elevenlabs.io/app/conversational-ai/{agent_id}",
            message="Voice AI Agent successfully deployed."
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Deployment failed: {str(exc)}")

