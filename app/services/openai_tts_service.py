import base64
import logging
from typing import Optional

from openai import OpenAI

from app.config import settings
from app.utils.audio_utils import mp3_to_twilio_payload, chunk_audio

logger = logging.getLogger(__name__)


def get_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


class OpenAITTS:
    """
    Text-to-speech using OpenAI TTS API.
    Optimised for low-latency phone call audio.
    """

    def __init__(
        self,
        voice: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.voice = voice or settings.openai_tts_voice
        self.model = model or settings.openai_tts_model
        self._client = get_openai_client()
        print(f"[OpenAI TTS] Initialized: model={self.model} voice={self.voice}")

    async def synthesize(self, text: str) -> bytes:
        """
        Convert text to MP3 audio bytes.
        Uses pcm format for fastest processing.
        """
        preview = text[:80] + "..." if len(text) > 80 else text
        print(f"[OpenAI TTS] Synthesizing: \"{preview}\"")

        try:
            response = self._client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format="mp3",
                speed=1.1,  # Slightly faster speech = shorter audio = less latency
            )

            audio_bytes = response.content
            print(f"[OpenAI TTS] Generated {len(audio_bytes)} bytes")
            logger.info(f"OpenAI TTS: {len(audio_bytes)} bytes for \"{text[:50]}\"")
            return audio_bytes

        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")
            print(f"[OpenAI TTS] ERROR: {e}")
            raise

    async def synthesize_for_twilio(self, text: str) -> list[str]:
        """
        Full pipeline: text → OpenAI MP3 → mulaw 8000Hz → base64 chunks
        """
        try:
            mp3_bytes = await self.synthesize(text)
            twilio_payload = mp3_to_twilio_payload(mp3_bytes)
            mulaw_bytes = base64.b64decode(twilio_payload)

            # Larger chunks = fewer WebSocket messages = faster delivery
            chunks = chunk_audio(mulaw_bytes, chunk_size=16000)

            encoded_chunks = [
                base64.b64encode(chunk).decode("utf-8")
                for chunk in chunks
            ]

            print(f"[OpenAI TTS] Ready for Twilio: {len(encoded_chunks)} chunks")
            return encoded_chunks

        except Exception as e:
            logger.error(f"OpenAI TTS synthesize_for_twilio error: {e}")
            print(f"[OpenAI TTS] synthesize_for_twilio ERROR: {e}")
            raise