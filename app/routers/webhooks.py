import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.call_record import CallRecord
from app.services.twilio_service import generate_greeting_twiml
from app.services.deepgram_service import (
    DeepgramTranscriber,
    register_transcriber,
    unregister_transcriber,
)
from app.utils.audio_utils import decode_mulaw_audio
from app.constants.app_constants import CallStatus, CallOutcome
from app.constants.messages import TWILIO_WEBHOOK_RECEIVED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

DEFAULT_CAMPAIGN_MESSAGE = (
    "This is NexusAI calling on behalf of your service provider. "
    "We have an important update for you."
)


@router.post("/call-answered", response_class=PlainTextResponse)
async def call_answered(
    request: Request,
    call_record_id: str,
    customer_name: str = "Valued Customer",
    db: Session = Depends(get_db),
):
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")

    logger.info(f"Call answered: SID={call_sid} call_record_id={call_record_id}")

    call_record = db.query(CallRecord).filter(
        CallRecord.id == call_record_id
    ).first()

    if call_record:
        call_record.status = CallStatus.IN_PROGRESS
        call_record.answered_at = datetime.utcnow()
        if call_sid:
            call_record.twilio_call_sid = call_sid
        db.commit()

    twiml = generate_greeting_twiml(
        customer_name=customer_name,
        campaign_message=DEFAULT_CAMPAIGN_MESSAGE,
        call_record_id=call_record_id,
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/call-status")
async def call_status_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "")
    call_duration = form_data.get("CallDuration", None)

    logger.info(
        TWILIO_WEBHOOK_RECEIVED.format(call_sid=call_sid)
        + f" status={call_status}"
    )

    call_record = db.query(CallRecord).filter(
        CallRecord.twilio_call_sid == call_sid
    ).first()

    if not call_record:
        logger.warning(f"No call record found for SID: {call_sid}")
        return {"status": "not_found"}

    status_map = {
        "initiated": CallStatus.IN_PROGRESS,
        "ringing": CallStatus.IN_PROGRESS,
        "answered": CallStatus.IN_PROGRESS,
        "in-progress": CallStatus.IN_PROGRESS,
        "completed": CallStatus.COMPLETED,
        "busy": CallStatus.BUSY,
        "no-answer": CallStatus.NO_ANSWER,
        "failed": CallStatus.FAILED,
        "canceled": CallStatus.CANCELLED,
    }

    new_status = status_map.get(call_status, call_record.status)
    call_record.status = new_status

    if call_status == "completed":
        call_record.ended_at = datetime.utcnow()
        call_record.outcome = CallOutcome.COMPLETED
        if call_duration:
            call_record.duration_seconds = int(call_duration)
    elif call_status in ("busy", "no-answer", "failed"):
        call_record.ended_at = datetime.utcnow()
        call_record.outcome = CallOutcome.UNRESOLVED
        call_record.error_message = f"Call ended with Twilio status: {call_status}"

    db.commit()
    logger.info(
        f"Call record {call_record.id} updated: "
        f"status={new_status} duration={call_duration}"
    )
    return {"status": "ok"}


@router.post("/call-completed")
async def call_completed(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    call_duration = form_data.get("CallDuration", 0)

    logger.info(f"Call completed: SID={call_sid} duration={call_duration}s")

    call_record = db.query(CallRecord).filter(
        CallRecord.twilio_call_sid == call_sid
    ).first()

    if call_record:
        call_record.status = CallStatus.COMPLETED
        call_record.ended_at = datetime.utcnow()
        call_record.duration_seconds = int(call_duration)
        call_record.outcome = CallOutcome.COMPLETED
        db.commit()

    return {"status": "ok"}


@router.websocket("/media-stream/{call_record_id}")
async def media_stream(
    websocket: WebSocket,
    call_record_id: str,
):
    """
    WebSocket endpoint that receives Twilio's audio stream.
    Forwards audio to Deepgram for real-time STT.
    """
    await websocket.accept()
    logger.info(f"Media stream WebSocket opened for call {call_record_id}")

    transcripts: list[str] = []

    async def on_interim(text: str):
        logger.info(f"Deepgram interim [{call_record_id}]: \"{text}\"")

    async def on_final(text: str):
        logger.info(f"Deepgram final [{call_record_id}]: \"{text}\"")
        transcripts.append(text)

    transcriber = DeepgramTranscriber(
        call_record_id=call_record_id,
        on_interim_transcript=on_interim,
        on_final_transcript=on_final,
    )
    register_transcriber(call_record_id, transcriber)

    try:
        # Start Deepgram connection — must happen before any audio arrives
        await transcriber.start()
        logger.info(f"Deepgram ready for call {call_record_id}")

        # Process incoming Twilio messages
        async for raw_message in websocket.iter_text():
            try:
                data = json.loads(raw_message)
                event = data.get("event", "")

                if event == "connected":
                    logger.info(
                        f"Twilio Media Stream connected for call {call_record_id}"
                    )

                elif event == "start":
                    stream_sid = data.get("streamSid", "")
                    logger.info(
                        f"Twilio stream started: streamSid={stream_sid} "
                        f"call={call_record_id}"
                    )

                elif event == "media":
                    payload = data.get("media", {}).get("payload", "")
                    if payload:
                        audio_bytes = decode_mulaw_audio(payload)
                        await transcriber.send_audio(audio_bytes)

                elif event == "stop":
                    logger.info(
                        f"Twilio stream stopped for call {call_record_id}"
                    )
                    break

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in media stream: {e}")
                continue

    except WebSocketDisconnect:
        logger.info(
            f"Media stream WebSocket disconnected for call {call_record_id}"
        )
    except Exception as e:
        logger.error(f"Media stream error for call {call_record_id}: {e}")
    finally:
        await transcriber.stop()
        unregister_transcriber(call_record_id)
        logger.info(
            f"Media stream closed for call {call_record_id}. "
            f"Total final transcripts: {len(transcripts)}"
        )