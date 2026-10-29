import io, asyncio, logging
from typing import AsyncGenerator
from elevenlabs.client import ElevenLabs
from app.core.config import settings

logger = logging.getLogger(__name__)
DEFAULT_ALERT_VOICE_ID = "onwK4e9ZLuTAKqWW03F9"

def get_elevenlabs_client() -> ElevenLabs:
    return ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

async def generate_intercept_audio_stream(warning_text: str, voice_id: str = DEFAULT_ALERT_VOICE_ID) -> bytes:
    client = get_elevenlabs_client()
    def _sync_tts_call() -> bytes:
        audio_stream = client.text_to_speech.convert(
            voice_id=voice_id, text=warning_text, model_id="eleven_flash_v2_5",
            output_format="pcm_16000", optimize_streaming_latency="4"
        )
        buffer = io.BytesIO()
        for chunk in audio_stream:
            if chunk: buffer.write(chunk)
        return buffer.getvalue()
    return await asyncio.to_thread(_sync_tts_call)

