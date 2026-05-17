import logging
from urllib.parse import quote

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream

from app.config import settings

logger = logging.getLogger(__name__)


def get_twilio_client() -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def initiate_call(
    to_phone_number: str,
    call_record_id: str,
    customer_name: str = "Valued Customer",
) -> dict:
    """
    Place an outbound call via Twilio.
    Returns a dict with call_sid and status.
    """
    client = get_twilio_client()

    status_callback_url = f"{settings.base_url}/webhooks/call-status"

    # URL-encode customer_name to handle spaces and special characters
    answered_url = (
        f"{settings.base_url}/webhooks/call-answered"
        f"?call_record_id={call_record_id}"
        f"&customer_name={quote(customer_name)}"
    )

    try:
        call = client.calls.create(
            to=to_phone_number,
            from_=settings.twilio_phone_number,
            url=answered_url,
            status_callback=status_callback_url,
            status_callback_method="POST",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            timeout=30,
        )
        logger.info(f"Twilio call initiated: SID={call.sid} to={to_phone_number}")
        return {"call_sid": call.sid, "status": call.status}

    except Exception as e:
        logger.error(f"Failed to initiate Twilio call to {to_phone_number}: {e}")
        raise


def generate_greeting_twiml(
    customer_name: str,
    campaign_message: str,
    call_record_id: str,
) -> str:
    """
    Generate TwiML that:
    1. Greets the customer with Alice's voice
    2. Opens a Media Stream WebSocket so we can hear the customer speak
    This enables real-time STT via Deepgram in Phase 5+
    """
    response = VoiceResponse()

    # Greet the customer
    response.say(
        f"Hello {customer_name}. {campaign_message}",
        voice="alice",
        language="en-IN",
    )
    response.pause(length=1)

    # Open Media Stream — Twilio will stream audio to our WebSocket
    connect = Connect()
    stream = Stream(
        url=f"wss://{settings.base_url.replace('https://', '')}"
            f"/webhooks/media-stream/{call_record_id}"
    )
    connect.append(stream)
    response.append(connect)

    return str(response)


def generate_voicemail_twiml(
    customer_name: str,
    campaign_message: str,
    call_record_id: str = "",
) -> str:
    """
    TwiML for when call goes to voicemail.
    """
    response = VoiceResponse()
    response.say(
        f"Hello {customer_name}. {campaign_message} "
        "Please call us back at your convenience. Thank you.",
        voice="alice",
        language="en-IN",
    )
    response.hangup()
    return str(response)


def end_call(call_sid: str) -> dict:
    """
    Hang up an active call by SID.
    """
    client = get_twilio_client()
    try:
        call = client.calls(call_sid).update(status="completed")
        logger.info(f"Call ended: SID={call_sid}")
        return {"call_sid": call.sid, "status": call.status}
    except Exception as e:
        logger.error(f"Failed to end call {call_sid}: {e}")
        raise


def get_call_status(call_sid: str) -> dict:
    """
    Fetch live call status from Twilio.
    """
    client = get_twilio_client()
    try:
        call = client.calls(call_sid).fetch()
        return {
            "call_sid": call.sid,
            "status": call.status,
            "duration": call.duration,
            "direction": call.direction,
            "from": call.from_,
            "to": call.to,
        }
    except Exception as e:
        logger.error(f"Failed to fetch call status for {call_sid}: {e}")
        raise