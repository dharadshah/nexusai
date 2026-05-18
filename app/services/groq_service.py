import json
import logging
from typing import Optional

from groq import Groq

from app.config import settings
from app.constants.app_constants import (
    CampaignType,
    Intent,
    MAX_CONVERSATION_TURNS,
)
from app.constants.prompts import (
    PAYMENT_REMINDER_SYSTEM_PROMPT,
    CUSTOMER_SUPPORT_SYSTEM_PROMPT,
    FEEDBACK_COLLECTION_SYSTEM_PROMPT,
    PROACTIVE_ENGAGEMENT_SYSTEM_PROMPT,
    INTENT_DETECTION_PROMPT,
    DEFAULT_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# Groq model to use — fastest available with strong reasoning
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_MAX_TOKENS = 80  # Keep responses short for phone calls
GROQ_TEMPERATURE = 0.7


def get_groq_client() -> Groq:
    return Groq(api_key=settings.groq_api_key)


def get_system_prompt(
    campaign_type: str,
    company_name: str = "NexusAI",
    **kwargs,
) -> str:
    """
    Select and format the system prompt for the given campaign type.
    kwargs are passed to the prompt template for dynamic values.
    """
    prompt_map = {
        CampaignType.PAYMENT_REMINDER: PAYMENT_REMINDER_SYSTEM_PROMPT,
        CampaignType.CUSTOMER_SUPPORT: CUSTOMER_SUPPORT_SYSTEM_PROMPT,
        CampaignType.FEEDBACK_COLLECTION: FEEDBACK_COLLECTION_SYSTEM_PROMPT,
        CampaignType.PROACTIVE_ENGAGEMENT: PROACTIVE_ENGAGEMENT_SYSTEM_PROMPT,
    }

    template = prompt_map.get(campaign_type, DEFAULT_SYSTEM_PROMPT)

    # Provide default values for template variables
    defaults = {
        "company_name": company_name,
        "amount": "the outstanding amount",
        "due_date": "as soon as possible",
        "case_summary": "the customer's issue",
        "feedback_topic": "our service",
        "engagement_reason": "an important update",
    }
    defaults.update(kwargs)

    try:
        return template.format(**defaults)
    except KeyError as e:
        logger.warning(f"Missing prompt variable: {e}. Using default.")
        return DEFAULT_SYSTEM_PROMPT.format(company_name=company_name)


class GroqConversationEngine:
    """
    Manages multi-turn conversation with Groq LLM.
    Maintains conversation history for context across turns.
    """

    def __init__(
        self,
        call_record_id: str,
        campaign_type: str,
        company_name: str = "NexusAI",
        system_prompt_override: Optional[str] = None,
        **prompt_kwargs,
    ):
        self.call_record_id = call_record_id
        self.campaign_type = campaign_type
        self.company_name = company_name
        self._client = get_groq_client()

        # Build system prompt
        if system_prompt_override:
            self.system_prompt = system_prompt_override
        else:
            self.system_prompt = get_system_prompt(
                campaign_type=campaign_type,
                company_name=company_name,
                **prompt_kwargs,
            )

        # Conversation history — grows with each turn
        self.history: list[dict] = []
        self.turn_count = 0
        self.last_intent = Intent.UNCLEAR

        print(f"[Groq] Engine created for call {call_record_id} "
              f"campaign_type={campaign_type}")

    def add_assistant_message(self, message: str):
        """
        Add an agent message to history (e.g. the opening greeting).
        """
        self.history.append({"role": "assistant", "content": message})

    def add_user_message(self, message: str):
        """
        Add a customer message to history.
        """
        self.history.append({"role": "user", "content": message})

    async def generate_response(self, customer_transcript: str) -> str:
        """
        Generate the agent's next response given the customer's transcript.
        Maintains full conversation history for context.
        """
        print(f"[Groq] Generating response for: \"{customer_transcript}\"")

        # Add customer message to history
        self.add_user_message(customer_transcript)
        self.turn_count += 1

        # Build messages array for Groq
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
        ]

        # Trim history if too long — keep system + last N turns
        if len(messages) > MAX_CONVERSATION_TURNS * 2 + 1:
            messages = [messages[0]] + messages[-(MAX_CONVERSATION_TURNS * 2):]

        try:
            completion = self._client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=GROQ_MAX_TOKENS,
                temperature=GROQ_TEMPERATURE,
            )

            response_text = completion.choices[0].message.content.strip()

            # Add agent response to history
            self.add_assistant_message(response_text)

            print(f"[Groq] Response: \"{response_text}\"")
            logger.info(
                f"Groq response [{self.call_record_id}] "
                f"turn={self.turn_count}: \"{response_text}\""
            )

            return response_text

        except Exception as e:
            logger.error(f"Groq generation error for call {self.call_record_id}: {e}")
            print(f"[Groq] ERROR: {e}")
            # Return a safe fallback response
            fallback = "I'm sorry, could you please repeat that?"
            self.add_assistant_message(fallback)
            return fallback

    async def detect_intent(self, transcript: str) -> dict:
        """
        Classify the customer's intent from their transcript.
        Returns a dict with intent, confidence, and reasoning.
        """
        try:
            prompt = INTENT_DETECTION_PROMPT.format(transcript=transcript)

            completion = self._client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.1,  # Low temperature for consistent classification
            )

            raw = completion.choices[0].message.content.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            result = json.loads(raw)

            # Validate intent value
            if result.get("intent") not in Intent.ALL:
                result["intent"] = Intent.UNCLEAR

            self.last_intent = result["intent"]

            print(
                f"[Groq] Intent detected: {result['intent']} "
                f"confidence={result.get('confidence')} "
                f"for: \"{transcript}\""
            )
            logger.info(
                f"Intent [{self.call_record_id}]: {result['intent']} "
                f"confidence={result.get('confidence')}"
            )

            return result

        except Exception as e:
            logger.error(
                f"Intent detection error for call {self.call_record_id}: {e}"
            )
            print(f"[Groq] Intent detection ERROR: {e}")
            return {
                "intent": Intent.UNCLEAR,
                "confidence": "low",
                "reasoning": "Could not detect intent",
            }

    def should_end_call(self) -> bool:
        """
        Determine if the call should be ended based on:
        - Current intent
        - Number of turns taken

        payment_declined alone does NOT end the call — the agent
        should try to reschedule. Only end on explicit goodbye,
        payment confirmed, or after max turns.
        """
        end_intents = {
            Intent.END_CALL,
            Intent.PAYMENT_CONFIRMED,
        }

        if self.last_intent in end_intents:
            print(
                f"[Groq] should_end_call=True "
                f"reason=intent:{self.last_intent}"
            )
            return True

        if self.turn_count >= MAX_CONVERSATION_TURNS:
            print(
                f"[Groq] should_end_call=True "
                f"reason=max_turns:{self.turn_count}"
            )
            return True

        return False

    def get_conversation_summary(self) -> list[dict]:
        """
        Return the full conversation history for saving to DB.
        """
        return self.history.copy()


# Registry of active conversation engines keyed by call_record_id
_active_engines: dict[str, GroqConversationEngine] = {}


def get_engine(call_record_id: str) -> Optional[GroqConversationEngine]:
    return _active_engines.get(call_record_id)


def register_engine(
    call_record_id: str,
    engine: GroqConversationEngine,
):
    _active_engines[call_record_id] = engine
    print(f"[Groq] Engine registered for call {call_record_id}")


def unregister_engine(call_record_id: str):
    _active_engines.pop(call_record_id, None)
    print(f"[Groq] Engine unregistered for call {call_record_id}")