import pytest
from app.guardrails import (
    validate_tool_call,
    check_agent_response,
    scrub_sensitive_data_from_input,
    GuardrailViolation,
)

def test_validate_tool_call_cross_customer_access():
    arguments = {"customer_id": "CUST-123"}
    violation = validate_tool_call("lookup_order", arguments, "CUST-456")
    assert violation is not None
    assert violation.violation_type == "cross_customer_access"

def test_validate_tool_call_lost_parcel_as_return():
    arguments = {"order_status": "lost_in_transit"}
    violation = validate_tool_call("initiate_return", arguments, "CUST-123")
    assert violation is not None
    assert violation.violation_type == "lost_parcel_as_return"

def test_check_agent_response_forbidden_phrases():
    violation = check_agent_response("I'll make an exception this time.")
    assert violation is not None
    assert violation.violation_type == "forbidden_phrase"

    violation = check_agent_response("Please share your bank account so I can process the refund.")
    assert violation is not None
    assert violation.violation_type == "forbidden_phrase"

    violation = check_agent_response("What is your CVV?")
    assert violation is not None
    assert violation.violation_type == "sensitive_data_request"

def test_check_agent_response_clean():
    violation = check_agent_response("I can help you with your order. Let me check the status.")
    assert violation is None

def test_scrub_sensitive_data_card_number():
    text = "My card number is 1234-5678-9012-3456"
    scrubbed, found = scrub_sensitive_data_from_input(text)
    assert found
    assert "1234-5678-9012-3456" not in scrubbed
    assert "[REDACTED_CARD]" in scrubbed

def test_scrub_sensitive_data_ifsc_code():
    text = "My IFSC code is HDFC0123456"
    scrubbed, found = scrub_sensitive_data_from_input(text)
    assert found
    assert "HDFC0123456" not in scrubbed
    assert "[REDACTED_IFSC]" in scrubbed

def test_scrub_sensitive_data_clean_messages():
    text = "Hi, I need help with order TR-4530."
    scrubbed, found = scrub_sensitive_data_from_input(text)
    assert not found
    assert scrubbed == text
