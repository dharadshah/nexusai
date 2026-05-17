class CallStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    CANCELLED = "cancelled"


class CallOutcome:
    PAYMENT_CONFIRMED = "payment_confirmed"
    PAYMENT_DECLINED = "payment_declined"
    CALLBACK_REQUESTED = "callback_requested"
    VOICEMAIL_LEFT = "voicemail_left"
    ESCALATED = "escalated"
    COMPLETED = "completed"
    UNRESOLVED = "unresolved"


class CampaignType:
    PAYMENT_REMINDER = "payment_reminder"
    CUSTOMER_SUPPORT = "customer_support"
    FEEDBACK_COLLECTION = "feedback_collection"
    PROACTIVE_ENGAGEMENT = "proactive_engagement"

    ALL = [
        PAYMENT_REMINDER,
        CUSTOMER_SUPPORT,
        FEEDBACK_COLLECTION,
        PROACTIVE_ENGAGEMENT,
    ]


class CampaignStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CustomerStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    DO_NOT_CALL = "do_not_call"


class Intent:
    PAYMENT_CONFIRMED = "payment_confirmed"
    PAYMENT_DECLINED = "payment_declined"
    CALLBACK_REQUESTED = "callback_requested"
    ESCALATION_REQUESTED = "escalation_requested"
    QUESTION_ASKED = "question_asked"
    END_CALL = "end_call"
    POSITIVE_RESPONSE = "positive_response"
    NEGATIVE_RESPONSE = "negative_response"
    UNCLEAR = "unclear"

    ALL = [
        PAYMENT_CONFIRMED,
        PAYMENT_DECLINED,
        CALLBACK_REQUESTED,
        ESCALATION_REQUESTED,
        QUESTION_ASKED,
        END_CALL,
        POSITIVE_RESPONSE,
        NEGATIVE_RESPONSE,
        UNCLEAR,
    ]


MAX_CALL_RETRIES = 3
MAX_CALL_DURATION_SECONDS = 300
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_CONVERSATION_TURNS = 10