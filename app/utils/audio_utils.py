import base64
import io
import logging

try:
    import audioop  # Python < 3.13
except ImportError:
    import audioop_lts as audioop  # Python 3.13+

from pydub import AudioSegment

logger = logging.getLogger(__name__)


def decode_mulaw_audio(payload: str) -> bytes:
    """
    Decode base64-encoded mulaw audio from Twilio Media Stream
    into raw bytes for Deepgram.
    """
    return base64.b64decode(payload)


def encode_audio_to_base64(audio_bytes: bytes) -> str:
    """
    Encode raw audio bytes to base64 string.
    """
    return base64.b64encode(audio_bytes).decode("utf-8")


def mp3_to_mulaw(mp3_bytes: bytes) -> bytes:
    """
    Convert MP3 audio bytes (from ElevenLabs) to
    mulaw 8000Hz mono (required by Twilio Media Stream).

    Pipeline:
        MP3 → PCM 16-bit 8000Hz mono → mulaw 8000Hz mono
    """
    try:
        audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(8000)
        audio = audio.set_sample_width(2)  # 16-bit = 2 bytes
        pcm_bytes = audio.raw_data
        mulaw_bytes = audioop.lin2ulaw(pcm_bytes, 2)
        return mulaw_bytes

    except Exception as e:
        logger.error(f"mp3_to_mulaw conversion error: {e}")
        raise


def mulaw_to_base64(mulaw_bytes: bytes) -> str:
    """
    Base64-encode mulaw audio bytes for sending
    back to Twilio over the Media Stream WebSocket.
    """
    return base64.b64encode(mulaw_bytes).decode("utf-8")


def mp3_to_twilio_payload(mp3_bytes: bytes) -> str:
    """
    Full pipeline: MP3 bytes → base64 mulaw string
    ready to send to Twilio Media Stream.
    """
    mulaw_bytes = mp3_to_mulaw(mp3_bytes)
    return mulaw_to_base64(mulaw_bytes)


def chunk_audio(audio_bytes: bytes, chunk_size: int = 8000) -> list[bytes]:
    """
    Split audio bytes into chunks for smooth streaming to Twilio.
    Default chunk size = 8000 bytes = ~0.5 seconds of mulaw audio.
    """
    chunks = []
    for i in range(0, len(audio_bytes), chunk_size):
        chunks.append(audio_bytes[i:i + chunk_size])
    return chunks