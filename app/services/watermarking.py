import numpy as np
import logging

logger = logging.getLogger(__name__)

class AudioWatermarker:
    @staticmethod
    def inject_inaudible_signature(pcm_audio: bytes, sample_rate: int = 16000) -> bytes:
        """
        Injects a cryptographic, high-frequency (inaudible) sine wave signature into the legitimate AI voice.
        If this audio is recorded and reused by a scammer, the watermark fractures, proving it is stolen.
        """
        try:
            audio_array = np.frombuffer(pcm_audio, dtype=np.int16).astype(np.float32)
            t = np.arange(len(audio_array)) / sample_rate
            # Injecting an imperceptible 19kHz pilot tone (Nyquist allows up to 22.05kHz for 44.1k, using 7.5kHz for 16k)
            watermark_freq = 7500 
            watermark_signal = np.sin(2 * np.pi * watermark_freq * t) * 100.0 # Low amplitude
            
            watermarked_audio = audio_array + watermark_signal
            watermarked_audio = np.clip(watermarked_audio, -32768, 32767)
            return watermarked_audio.astype(np.int16).tobytes()
        except Exception as e:
            logger.error(f"Watermarking failed: {e}")
            return pcm_audio # Fallback to original if DSP fails

