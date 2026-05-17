import asyncio
import pytest
from app.services.groq_service import (
    GroqConversationEngine,
    get_system_prompt,
)
from app.constants.app_constants import CampaignType, Intent


def test_get_system_prompt_payment():
    prompt = get_system_prompt(
        campaign_type=CampaignType.PAYMENT_REMINDER,
        company_name="TestBank",
        amount="5000",
        due_date="30th May 2026",
    )
    assert "TestBank" in prompt
    assert "5000" in prompt
    assert "30th May 2026" in prompt


def test_get_system_prompt_fallback():
    prompt = get_system_prompt(
        campaign_type="unknown_type",
        company_name="TestCo",
    )
    assert "TestCo" in prompt


def test_engine_add_messages():
    engine = GroqConversationEngine(
        call_record_id="test-001",
        campaign_type=CampaignType.PAYMENT_REMINDER,
        company_name="TestBank",
    )
    engine.add_assistant_message("Hello, this is TestBank calling.")
    engine.add_user_message("Yes, who is this?")
    assert len(engine.history) == 2
    assert engine.history[0]["role"] == "assistant"
    assert engine.history[1]["role"] == "user"


def test_engine_should_end_call_max_turns():
    engine = GroqConversationEngine(
        call_record_id="test-002",
        campaign_type=CampaignType.PAYMENT_REMINDER,
        company_name="TestBank",
    )
    engine.turn_count = 10
    assert engine.should_end_call() is True


def test_engine_should_end_call_intent():
    engine = GroqConversationEngine(
        call_record_id="test-003",
        campaign_type=CampaignType.PAYMENT_REMINDER,
        company_name="TestBank",
    )
    engine.last_intent = Intent.END_CALL
    assert engine.should_end_call() is True


def test_engine_should_not_end_call():
    engine = GroqConversationEngine(
        call_record_id="test-004",
        campaign_type=CampaignType.PAYMENT_REMINDER,
        company_name="TestBank",
    )
    engine.last_intent = Intent.QUESTION_ASKED
    engine.turn_count = 2
    assert engine.should_end_call() is False


@pytest.mark.asyncio
async def test_generate_response_live():
    """
    Live test — calls the actual Groq API.
    Requires GROQ_API_KEY in .env
    """
    engine = GroqConversationEngine(
        call_record_id="test-live-001",
        campaign_type=CampaignType.PAYMENT_REMINDER,
        company_name="NexusAI",
        amount="2500",
        due_date="31st May 2026",
    )
    engine.add_assistant_message(
        "Hello, this is NexusAI calling about your payment."
    )
    response = await engine.generate_response(
        "Hi, yes I know about the payment. Can I pay tomorrow?"
    )
    assert isinstance(response, str)
    assert len(response) > 0
    print(f"\nGroq live response: {response}")


@pytest.mark.asyncio
async def test_detect_intent_live():
    """
    Live test — calls the actual Groq API.
    """
    engine = GroqConversationEngine(
        call_record_id="test-live-002",
        campaign_type=CampaignType.PAYMENT_REMINDER,
        company_name="NexusAI",
    )
    result = await engine.detect_intent(
        "Yes, I will make the payment right now."
    )
    assert result["intent"] in Intent.ALL
    assert result["confidence"] in ["high", "medium", "low"]
    print(f"\nIntent result: {result}")