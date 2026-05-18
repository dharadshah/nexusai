import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services.conversation_engine import ConversationEngine
from app.models.campaign import Campaign
from app.models.customer import Customer
from app.constants.app_constants import CampaignType

logger = logging.getLogger(__name__)

# Registry of active call agents keyed by call_record_id
_active_agents: dict[str, ConversationEngine] = {}


def get_agent(call_record_id: str) -> Optional[ConversationEngine]:
    return _active_agents.get(call_record_id)


def register_agent(call_record_id: str, engine: ConversationEngine):
    _active_agents[call_record_id] = engine
    print(f"[Agent] Registered for call {call_record_id}")


def unregister_agent(call_record_id: str):
    _active_agents.pop(call_record_id, None)
    print(f"[Agent] Unregistered for call {call_record_id}")


def build_conversation_engine(
    call_record_id: str,
    customer: Customer,
    campaign: Campaign,
    websocket,
    db: Session,
) -> ConversationEngine:
    """
    Build a ConversationEngine from a Customer and Campaign.
    Extracts all relevant context from the campaign to pass
    to the LLM prompt templates.
    """
    print(
        f"[Agent] Building engine: "
        f"customer={customer.full_name} "
        f"campaign={campaign.name} "
        f"type={campaign.campaign_type}"
    )

    # Build prompt kwargs based on campaign type
    prompt_kwargs = _build_prompt_kwargs(campaign)

    engine = ConversationEngine(
        call_record_id=call_record_id,
        customer_name=customer.full_name,
        campaign_type=campaign.campaign_type,
        company_name=campaign.company_name,
        system_prompt_override=campaign.system_prompt_override or None,
        websocket=websocket,
        db=db,
        **prompt_kwargs,
    )

    return engine


def _build_prompt_kwargs(campaign: Campaign) -> dict:
    """
    Extract campaign metadata into prompt template variables.
    """
    kwargs = {}

    if campaign.campaign_type == CampaignType.PAYMENT_REMINDER:
        metadata = {}
        try:
            import json
            if hasattr(campaign, '_metadata') and campaign._metadata:
                metadata = json.loads(campaign._metadata)
        except Exception:
            pass

        kwargs["amount"] = metadata.get("amount", "the outstanding amount")
        kwargs["due_date"] = metadata.get("due_date", "as soon as possible")

    elif campaign.campaign_type == CampaignType.CUSTOMER_SUPPORT:
        kwargs["case_summary"] = campaign.description or "the customer's issue"

    elif campaign.campaign_type == CampaignType.FEEDBACK_COLLECTION:
        kwargs["feedback_topic"] = campaign.description or "our service"

    elif campaign.campaign_type == CampaignType.PROACTIVE_ENGAGEMENT:
        kwargs["engagement_reason"] = campaign.description or "an important update"

    return kwargs