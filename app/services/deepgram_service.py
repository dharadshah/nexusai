import asyncio
import logging
from typing import Callable, Optional

from deepgram import AsyncDeepgramClient
from deepgram.listen.v1.socket_client import AsyncV1SocketClient, EventType
from deepgram.listen.v1.socket_client import ListenV1Results

from app.config import settings

logger = logging.getLogger(__name__)


class DeepgramTranscriber:
    """
    Manages a real-time streaming STT connection to Deepgram v7.
    Receives raw mulaw audio from Twilio and returns transcripts.
    """

    def __init__(
        self,
        call_record_id: str,
        on_interim_transcript: Optional[Callable] = None,
        on_final_transcript: Optional[Callable] = None,
    ):
        self.call_record_id = call_record_id
        self.on_interim_transcript = on_interim_transcript
        self.on_final_transcript = on_final_transcript
        self._socket: Optional[AsyncV1SocketClient] = None
        self._context_manager = None
        self.is_connected = False
        self._client = None

    async def start(self):
        """
        Open a streaming WebSocket connection to Deepgram.
        """
        print(f"[Deepgram] Starting connection for call {self.call_record_id}")
        try:
            self._client = AsyncDeepgramClient(api_key=settings.deepgram_api_key)
            print(f"[Deepgram] Client created for call {self.call_record_id}")

            self._context_manager = self._client.listen.v1.connect(
                model="nova-2",
                language="en-IN",
                encoding="mulaw",
                sample_rate=8000,
                channels=1,
                interim_results=True,
                endpointing=300,
                utterance_end_ms="1000",
                smart_format=True,
            )

            print(f"[Deepgram] Entering context manager for call {self.call_record_id}")
            self._socket = await self._context_manager.__aenter__()
            print(f"[Deepgram] Socket created: {self._socket} for call {self.call_record_id}")

            # Register event handlers
            self._socket.on(EventType.MESSAGE, self._on_message)
            self._socket.on(EventType.ERROR, self._on_error)
            self._socket.on(EventType.CLOSE, self._on_close)

            # Start the listening loop in the background
            asyncio.create_task(self._socket.start_listening())
            print(f"[Deepgram] Listening task created for call {self.call_record_id}")

            self.is_connected = True
            print(f"[Deepgram] Ready — is_connected=True for call {self.call_record_id}")

        except Exception as e:
            print(f"[Deepgram] START ERROR for call {self.call_record_id}: {e}")
            logger.error(
                f"Deepgram start error for call {self.call_record_id}: {e}"
            )
            raise

    async def send_audio(self, audio_bytes: bytes):
        """
        Send raw mulaw audio bytes to Deepgram for transcription.
        """
        if self._socket and self.is_connected:
            try:
                await self._socket.send_media(audio_bytes)
            except Exception as e:
                print(f"[Deepgram] send audio error: {e}")
                logger.error(f"Deepgram send audio error: {e}")

    async def stop(self):
        """
        Close the Deepgram connection cleanly.
        """
        print(f"[Deepgram] Stopping for call {self.call_record_id}")
        if self._socket and self.is_connected:
            try:
                await self._socket.send_close_stream()
                if self._context_manager:
                    await self._context_manager.__aexit__(None, None, None)
                self.is_connected = False
                print(f"[Deepgram] Stopped for call {self.call_record_id}")
            except Exception as e:
                print(f"[Deepgram] stop error: {e}")
                logger.error(f"Deepgram stop error: {e}")

    def _on_message(self, message):
        """
        Handle incoming transcript messages from Deepgram.
        """
        try:
            print(f"[Deepgram] Message received: {type(message).__name__}")
            if not isinstance(message, ListenV1Results):
                return

            alternatives = (
                message.channel.alternatives if message.channel else []
            )
            if not alternatives:
                return

            transcript = alternatives[0].transcript
            if not transcript:
                return

            is_final = message.is_final

            if is_final:
                print(f"[Deepgram] FINAL [{self.call_record_id}]: \"{transcript}\"")
                logger.info(
                    f"Deepgram final [{self.call_record_id}]: \"{transcript}\""
                )
                if self.on_final_transcript:
                    asyncio.create_task(
                        self._safe_callback(self.on_final_transcript, transcript)
                    )
            else:
                print(f"[Deepgram] interim [{self.call_record_id}]: \"{transcript}\"")
                logger.info(
                    f"Deepgram interim [{self.call_record_id}]: \"{transcript}\""
                )
                if self.on_interim_transcript:
                    asyncio.create_task(
                        self._safe_callback(self.on_interim_transcript, transcript)
                    )

        except Exception as e:
            print(f"[Deepgram] message handler error: {e}")
            logger.error(f"Deepgram message handler error: {e}")

    def _on_error(self, error):
        print(f"[Deepgram] ERROR [{self.call_record_id}]: {error}")
        logger.error(
            f"Deepgram error for call {self.call_record_id}: {error}"
        )
        self.is_connected = False

    def _on_close(self, event):
        print(f"[Deepgram] CLOSED [{self.call_record_id}]")
        logger.info(
            f"Deepgram connection closed for call {self.call_record_id}"
        )
        self.is_connected = False

    async def _safe_callback(self, callback: Callable, *args):
        """
        Call a callback safely — handles both sync and async callbacks.
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            print(f"[Deepgram] callback error: {e}")
            logger.error(f"Deepgram callback error: {e}")


# Registry of active transcribers keyed by call_record_id
_active_transcribers: dict[str, DeepgramTranscriber] = {}


def get_transcriber(call_record_id: str) -> Optional[DeepgramTranscriber]:
    return _active_transcribers.get(call_record_id)


def register_transcriber(
    call_record_id: str,
    transcriber: DeepgramTranscriber,
):
    _active_transcribers[call_record_id] = transcriber
    print(f"[Deepgram] Transcriber registered for call {call_record_id}")


def unregister_transcriber(call_record_id: str):
    _active_transcribers.pop(call_record_id, None)
    print(f"[Deepgram] Transcriber unregistered for call {call_record_id}")