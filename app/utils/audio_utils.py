import base64


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