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
    Drop-in replacement for ElevenLabsTTS.
    Converts Groq response text into audio
    ready to stream back over Twilio Media Stream.
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
        Convert text to MP3 audio bytes using OpenAI TTS.
        Returns raw MP3 bytes.
        """
        preview = text[:80] + "..." if len(text) > 80 else text
        print(f"[OpenAI TTS] Synthesizing: \"{preview}\"")

        try:
            response = self._client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format="mp3",
            )

            audio_bytes = response.content

            print(f"[OpenAI TTS] Generated {len(audio_bytes)} bytes")
            logger.info(
                f"OpenAI TTS synthesized {len(audio_bytes)} bytes "
                f"for: \"{text[:50]}\""
            )

            return audio_bytes

        except Exception as e:
            logger.error(f"OpenAI TTS synthesis error: {e}")
            print(f"[OpenAI TTS] ERROR: {e}")
            raise

    async def synthesize_for_twilio(self, text: str) -> list[str]:
        """
        Full pipeline:
        text → OpenAI MP3 → mulaw 8000Hz → base64 chunks
        Returns list of base64-encoded mulaw chunks
        ready to send over Twilio Media Stream WebSocket.
        """
        try:
            # Step 1 — Generate MP3 from OpenAI
            mp3_bytes = await self.synthesize(text)

            # Step 2 — Convert MP3 to Twilio-compatible mulaw base64
            twilio_payload = mp3_to_twilio_payload(mp3_bytes)

            # Step 3 — Decode back to bytes for chunking
            mulaw_bytes = base64.b64decode(twilio_payload)

            # Step 4 — Split into chunks for smooth playback
            chunks = chunk_audio(mulaw_bytes, chunk_size=8000)

            # Step 5 — Re-encode each chunk to base64
            encoded_chunks = [
                base64.b64encode(chunk).decode("utf-8")
                for chunk in chunks
            ]

            print(
                f"[OpenAI TTS] Ready for Twilio: "
                f"{len(encoded_chunks)} chunks"
            )
            return encoded_chunks

        except Exception as e:
            logger.error(f"OpenAI TTS synthesize_for_twilio error: {e}")
            print(f"[OpenAI TTS] synthesize_for_twilio ERROR: {e}")
            raise