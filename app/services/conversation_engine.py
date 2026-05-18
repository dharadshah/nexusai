import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.services.deepgram_service import DeepgramTranscriber
from app.services.groq_service import GroqConversationEngine
from app.services.openai_tts_service import OpenAITTS
from app.models.call_record import CallRecord
from app.models.conversation import Conversation
from app.constants.app_constants import CallOutcome, Intent

logger = logging.getLogger(__name__)


class ConversationEngine:
    """
    Wires together STT (Deepgram) + LLM (Groq) + TTS (OpenAI)
    into a single real-time conversation loop.
    """

    def __init__(
        self,
        call_record_id: str,
        customer_name: str,
        campaign_type: str,
        company_name: str = "NexusAI",
        system_prompt_override: Optional[str] = None,
        websocket=None,
        db: Optional[Session] = None,
        **prompt_kwargs,
    ):
        self.call_record_id = call_record_id
        self.customer_name = customer_name
        self.campaign_type = campaign_type
        self.websocket = websocket
        self.db = db
        self.stream_sid: Optional[str] = None
        self.is_agent_speaking = False
        self.turn_number = 0
        self._greeting_sent = False

        self.tts = OpenAITTS()
        self.llm = GroqConversationEngine(
            call_record_id=call_record_id,
            campaign_type=campaign_type,
            company_name=company_name,
            system_prompt_override=system_prompt_override,
            **prompt_kwargs,
        )
        self.stt = DeepgramTranscriber(
            call_record_id=call_record_id,
            on_interim_transcript=self._on_interim,
            on_final_transcript=self._on_final_transcript,
        )

        print(f"[Engine] ConversationEngine created for call {call_record_id}")

    async def start(self):
        """
        Start Deepgram STT connection.
        Greeting is sent after stream_sid is received.
        """
        print(f"[Engine] Starting for call {self.call_record_id}")
        await self.stt.start()
        print(f"[Engine] Deepgram ready for call {self.call_record_id}")

    async def process_audio(self, audio_bytes: bytes):
        """
        Forward raw audio from Twilio to Deepgram.
        Skipped while agent is speaking.
        """
        if not self.is_agent_speaking:
            await self.stt.send_audio(audio_bytes)

    def set_stream_sid(self, stream_sid: str):
        """
        Called when Twilio sends the 'start' event.
        This is the signal to send the opening greeting.
        """
        self.stream_sid = stream_sid
        print(f"[Engine] stream_sid set: {stream_sid}")

        # Now that we have the stream_sid, send the greeting
        if not self._greeting_sent:
            asyncio.create_task(self._send_greeting())

    async def _send_greeting(self):
        """
        Generate and send the opening greeting via OpenAI TTS.
        Called once stream_sid is available.
        """
        self._greeting_sent = True
        greeting = (
            f"Hello, may I speak with {self.customer_name}? "
            f"This is NexusAI calling."
        )
        self.llm.add_assistant_message(greeting)
        await self._speak(greeting)
        print(f"[Engine] Greeting sent for call {self.call_record_id}")

    async def _on_interim(self, text: str):
        print(f"[Engine] Interim: \"{text}\"")

    async def _on_final_transcript(self, text: str):
        """
        Full pipeline: transcript → intent → response → audio.
        """
        if self.is_agent_speaking:
            print(f"[Engine] Ignoring transcript (agent speaking): \"{text}\"")
            return

        print(f"[Engine] Final transcript: \"{text}\"")
        self.turn_number += 1

        await self._save_conversation_turn(speaker="customer", message=text)

        # Run intent detection and response generation in parallel
        intent_task = asyncio.create_task(self.llm.detect_intent(text))
        response_task = asyncio.create_task(self.llm.generate_response(text))

        intent_result, response = await asyncio.gather(intent_task, response_task)
        intent = intent_result.get("intent", Intent.UNCLEAR)
        print(f"[Engine] Intent: {intent}")

        # Update LLM turn count for should_end_call check
        if self.llm.should_end_call():
            farewell = "Thank you for your time. Have a great day. Goodbye!"
            await self._speak(farewell)
            await self._save_conversation_turn(
                speaker="agent",
                message=farewell,
                intent_detected=intent,
            )
            await self._end_call(intent)
            return
        await self._save_conversation_turn(
            speaker="agent",
            message=response,
            intent_detected=intent,
        )
        await self._speak(response)

    async def _speak(self, text: str):
        """
        Convert text to audio and send over Twilio WebSocket.
        Pauses Deepgram while speaking to avoid echo.
        """
        if not self.websocket or not self.stream_sid:
            print(f"[Engine] Cannot speak — no websocket or stream_sid")
            return

        self.is_agent_speaking = True
        self.stt.pause()  # Pause Deepgram — keepalive maintains connection
        print(f"[Engine] Speaking: \"{text[:80]}\"")

        try:
            chunks = await self.tts.synthesize_for_twilio(text)

            for chunk in chunks:
                await self.websocket.send_text(json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": chunk},
                }))

            await self.websocket.send_text(json.dumps({
                "event": "mark",
                "streamSid": self.stream_sid,
                "mark": {"name": "agent_done_speaking"},
            }))

            print(f"[Engine] Audio sent: {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"[Engine] _speak error: {e}")
            print(f"[Engine] _speak ERROR: {e}")
        finally:
            self.is_agent_speaking = False
            self.stt.resume()  # Resume Deepgram after speaking

    async def _save_conversation_turn(
        self,
        speaker: str,
        message: str,
        intent_detected: Optional[str] = None,
    ):
        if not self.db:
            return
        try:
            turn = Conversation(
                call_record_id=self.call_record_id,
                turn_number=self.turn_number,
                speaker=speaker,
                message=message,
                intent_detected=intent_detected,
            )
            self.db.add(turn)
            self.db.commit()
            print(f"[Engine] Saved turn {self.turn_number}: {speaker}: \"{message[:50]}\"")
        except Exception as e:
            logger.error(f"[Engine] DB save error: {e}")
            print(f"[Engine] DB save ERROR: {e}")

    async def _end_call(self, final_intent: str):
        if not self.db:
            return
        try:
            call_record = self.db.query(CallRecord).filter(
                CallRecord.id == self.call_record_id
            ).first()
            if call_record:
                # Use last meaningful intent to determine outcome
                last_intent = self.llm.last_intent
                outcome_map = {
                    Intent.PAYMENT_CONFIRMED: CallOutcome.PAYMENT_CONFIRMED,
                    Intent.PAYMENT_DECLINED: CallOutcome.PAYMENT_DECLINED,
                    Intent.CALLBACK_REQUESTED: CallOutcome.CALLBACK_REQUESTED,
                    Intent.ESCALATION_REQUESTED: CallOutcome.ESCALATED,
                }
                call_record.outcome = outcome_map.get(
                    last_intent,
                    outcome_map.get(final_intent, CallOutcome.COMPLETED)
                )
                call_record.ended_at = datetime.utcnow()
                self.db.commit()
                print(f"[Engine] Call outcome saved: {call_record.outcome}")
        except Exception as e:
            logger.error(f"[Engine] _end_call DB error: {e}")

    async def stop(self):
        print(f"[Engine] Stopping for call {self.call_record_id}")
        await self.stt.stop()
        print(f"[Engine] Stopped for call {self.call_record_id}")

    def get_transcript_summary(self) -> list[dict]:
        return self.llm.get_conversation_summary()