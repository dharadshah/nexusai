import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.conversation_engine import ConversationEngine
from app.constants.app_constants import CampaignType, Intent


@pytest.fixture
def mock_websocket():
    ws = MagicMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def engine(mock_websocket, mock_db):
    return ConversationEngine(
        call_record_id="test-call-001",
        customer_name="Dhara Shah",
        campaign_type=CampaignType.PAYMENT_REMINDER,
        company_name="NexusAI",
        websocket=mock_websocket,
        db=mock_db,
        amount="5000",
        due_date="31st May 2026",
    )


def test_engine_initialises(engine):
    assert engine.call_record_id == "test-call-001"
    assert engine.customer_name == "Dhara Shah"
    assert engine.campaign_type == CampaignType.PAYMENT_REMINDER
    assert engine.is_agent_speaking is False
    assert engine.turn_number == 0
    assert engine.stream_sid is None


@pytest.mark.asyncio
async def test_set_stream_sid(engine):
    engine.set_stream_sid("MX12345")
    assert engine.stream_sid == "MX12345"


def test_engine_has_all_services(engine):
    assert engine.stt is not None
    assert engine.llm is not None
    assert engine.tts is not None


def test_llm_history_empty_on_start(engine):
    assert len(engine.llm.history) == 0


def test_turn_number_increments(engine):
    assert engine.turn_number == 0
    engine.turn_number += 1
    assert engine.turn_number == 1


def test_should_end_call_false_initially(engine):
    assert engine.llm.should_end_call() is False


def test_should_end_call_true_at_max_turns(engine):
    engine.llm.turn_count = 10
    assert engine.llm.should_end_call() is True


def test_should_end_call_true_on_end_intent(engine):
    engine.llm.last_intent = Intent.PAYMENT_CONFIRMED
    assert engine.llm.should_end_call() is True


@pytest.mark.asyncio
async def test_speak_requires_stream_sid(engine, mock_websocket):
    # No stream_sid set — should not send anything
    engine.stream_sid = None
    await engine._speak("Hello test")
    mock_websocket.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_on_interim_does_not_trigger_llm(engine):
    with patch.object(engine.llm, 'generate_response', new_callable=AsyncMock) as mock_gen:
        await engine._on_interim("partial text")
        mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_ignores_transcript_while_speaking(engine):
    engine.is_agent_speaking = True
    with patch.object(engine.llm, 'generate_response', new_callable=AsyncMock) as mock_gen:
        await engine._on_final_transcript("hello")
        mock_gen.assert_not_called()


def test_get_transcript_summary_empty(engine):
    summary = engine.get_transcript_summary()
    assert isinstance(summary, list)
    assert len(summary) == 0