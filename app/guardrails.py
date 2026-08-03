import re
from typing import Optional

_BANK_ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")
_CARD_NUMBER_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_CVV_RE = re.compile(r"\bcvv\b", re.IGNORECASE)
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")

_FORBIDDEN_PHRASES = [
    "as a special exception",
    "i'll make an exception",
    "one-time courtesy",
    "i can offer you a discount",
    "let me apply a coupon",
    "complimentary",
    "free of charge as a gesture",
    "i'll waive",
    "goodwill gesture",
    "here is your bank account",
    "your card number is",
    "what is your card number",
    "please share your bank",
    "please provide your bank account",
    "please share your upi",
    "share your cvv",
]


class GuardrailViolation(Exception):
    def __init__(self, violation_type: str, message: str):
        self.violation_type = violation_type
        self.message = message
        super().__init__(message)


def validate_tool_call(tool_name: str, arguments: dict, current_customer_id: str) -> Optional[GuardrailViolation]:
    if "customer_id" in arguments:
        if arguments["customer_id"] != current_customer_id:
            return GuardrailViolation(
                "cross_customer_access",
                f"Blocked: attempted to access data for customer "
                f"{arguments['customer_id']} while serving {current_customer_id}.",
            )

    if tool_name in ("initiate_return", "initiate_exchange"):
        if arguments.get("order_status") == "lost_in_transit":
            return GuardrailViolation(
                "lost_parcel_as_return",
                "Blocked: lost-in-transit orders must be escalated to a human agent, "
                "not processed as returns.",
            )

    return None


def check_agent_response(response_text: str) -> Optional[GuardrailViolation]:
    lower = response_text.lower()

    for phrase in _FORBIDDEN_PHRASES:
        if phrase in lower:
            return GuardrailViolation("forbidden_phrase", f"Response contains forbidden phrase: '{phrase}'")

    if _CVV_RE.search(response_text):
        return GuardrailViolation("sensitive_data_request", "Response appears to request CVV information.")

    return None


def scrub_sensitive_data_from_input(user_message: str) -> tuple[str, bool]:
    scrubbed = user_message
    found = False

    if _CARD_NUMBER_RE.search(scrubbed):
        scrubbed = _CARD_NUMBER_RE.sub("[REDACTED_CARD]", scrubbed)
        found = True

    if _IFSC_RE.search(scrubbed):
        scrubbed = _IFSC_RE.sub("[REDACTED_IFSC]", scrubbed)
        found = True

    return scrubbed, found
