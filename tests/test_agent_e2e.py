import os
import pytest
from app.agent import TrendlyAgent

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
skip_no_key = pytest.mark.skipif(not GROQ_API_KEY, reason="GROQ_API_KEY not set")


@skip_no_key
def test_happy_path_order_lookup():
    agent = TrendlyAgent(api_key=GROQ_API_KEY)
    result = agent.chat("test-hp-1", "C-101", "Can you check order TR-4530 for me?")
    assert "TR-4530" in result["response"] or "Block-Print Kurta" in result["response"]
    assert not result["escalated"]


@skip_no_key
def test_jewellery_return_refused():
    agent = TrendlyAgent(api_key=GROQ_API_KEY)
    result = agent.chat("test-jr-1", "C-102", "I want to return the Pearl Drop Earrings from order TR-4527")
    lower = result["response"].lower()
    assert "jewellery" in lower or "non-returnable" in lower or "cannot" in lower
    assert not result["escalated"]


@skip_no_key
def test_lost_parcel_escalation():
    agent = TrendlyAgent(api_key=GROQ_API_KEY)
    result = agent.chat("test-lp-1", "C-101", "What's happening with my order TR-4526? It's been weeks!")
    assert result["escalated"] or "human agent" in result["response"].lower() or "escalat" in result["response"].lower()


@skip_no_key
def test_cancelled_order_return():
    agent = TrendlyAgent(api_key=GROQ_API_KEY)
    result = agent.chat("test-co-1", "C-100", "I'd like to return the Silk Scarf from order TR-4529")
    lower = result["response"].lower()
    assert "cancelled" in lower or "cannot" in lower


@skip_no_key
def test_discount_request_refused():
    agent = TrendlyAgent(api_key=GROQ_API_KEY)
    result = agent.chat("test-dr-1", "C-100", "Can you give me a 20% discount on my next order? I've been a loyal customer.")
    lower = result["response"].lower()
    assert "discount" in lower or "unable" in lower or "cannot" in lower or "not able" in lower
