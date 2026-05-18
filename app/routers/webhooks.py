import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.call_record import CallRecord
from app.models.customer import Customer
from app.models.campaign import Campaign
from app.services.twilio_service import generate_stream_twiml
from app.agents.call_agent import (
    build_conversation_engine,
    register_agent,
    unregister_agent,
)
from app.utils.audio_utils import decode_mulaw_audio
from app.constants.app_constants import CallStatus, CallOutcome
from app.constants.messages import TWILIO_WEBHOOK_RECEIVED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/call-answered", response_class=PlainTextResponse)
async def call_answered(
    request: Request,
    call_record_id: str,
    customer_name: str = "Valued Customer",
    db: Session = Depends(get_db),
):
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    print(f"[Webhook] Call answered: SID={call_sid}")

    call_record = db.query(CallRecord).filter(
        CallRecord.id == call_record_id
    ).first()

    if call_record:
        call_record.status = CallStatus.IN_PROGRESS
        call_record.answered_at = datetime.utcnow()
        if call_sid:
            call_record.twilio_call_sid = call_sid
        db.commit()

    twiml = generate_stream_twiml(call_record_id=call_record_id)
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
        if not call_record.outcome or call_record.outcome == CallOutcome.UNRESOLVED:
            call_record.outcome = CallOutcome.COMPLETED
        if call_duration:
            call_record.duration_seconds = int(call_duration)
    elif call_status in ("busy", "no-answer", "failed"):
        call_record.ended_at = datetime.utcnow()
        call_record.outcome = CallOutcome.UNRESOLVED
        call_record.error_message = f"Call ended with status: {call_status}"

    db.commit()
    return {"status": "ok"}


@router.post("/call-completed")
async def call_completed(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    call_duration = form_data.get("CallDuration", 0)

    call_record = db.query(CallRecord).filter(
        CallRecord.twilio_call_sid == call_sid
    ).first()

    if call_record:
        call_record.status = CallStatus.COMPLETED
        call_record.ended_at = datetime.utcnow()
        call_record.duration_seconds = int(call_duration)
        if not call_record.outcome or call_record.outcome == CallOutcome.UNRESOLVED:
            call_record.outcome = CallOutcome.COMPLETED
        db.commit()

    return {"status": "ok"}


@router.websocket("/media-stream/{call_record_id}")
async def media_stream(
    websocket: WebSocket,
    call_record_id: str,
):
    """
    WebSocket endpoint — full ConversationEngine loop.
    STT (Deepgram) + LLM (Groq) + TTS (OpenAI) all wired together.
    """
    await websocket.accept()
    print(f"[Webhook] Media stream opened for call {call_record_id}")

    db = SessionLocal()

    try:
        call_record = db.query(CallRecord).filter(
            CallRecord.id == call_record_id
        ).first()

        if not call_record:
            print(f"[Webhook] Call record not found: {call_record_id}")
            await websocket.close()
            return

        customer = db.query(Customer).filter(
            Customer.id == call_record.customer_id
        ).first()

        campaign = db.query(Campaign).filter(
            Campaign.id == call_record.campaign_id
        ).first()

        if not customer or not campaign:
            print(f"[Webhook] Customer or campaign not found")
            await websocket.close()
            return

        engine = build_conversation_engine(
            call_record_id=call_record_id,
            customer=customer,
            campaign=campaign,
            websocket=websocket,
            db=db,
        )
        register_agent(call_record_id, engine)

        await engine.start()

        async for raw_message in websocket.iter_text():
            try:
                data = json.loads(raw_message)
                event = data.get("event", "")

                if event == "connected":
                    print(f"[Twilio] Stream connected for call {call_record_id}")

                elif event == "start":
                    stream_sid = data.get("streamSid", "")
                    engine.set_stream_sid(stream_sid)
                    print(f"[Twilio] Stream started: streamSid={stream_sid}")

                elif event == "media":
                    payload = data.get("media", {}).get("payload", "")
                    if payload:
                        audio_bytes = decode_mulaw_audio(payload)
                        await engine.process_audio(audio_bytes)

                elif event == "mark":
                    mark_name = data.get("mark", {}).get("name", "")
                    print(f"[Twilio] Mark: {mark_name}")

                elif event == "stop":
                    print(f"[Twilio] Stream stopped for call {call_record_id}")
                    break

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                continue

    except WebSocketDisconnect:
        print(f"[Webhook] WebSocket disconnected for call {call_record_id}")
    except Exception as e:
        logger.error(f"Media stream error for call {call_record_id}: {e}")
        print(f"[Webhook] ERROR: {e}")
    finally:
        if 'engine' in locals():
            await engine.stop()
            summary = engine.get_transcript_summary()
            print(f"[Webhook] Call ended. Total turns: {len(summary)}")
        unregister_agent(call_record_id)
        db.close()
        print(f"[Webhook] Media stream closed for call {call_record_id}")