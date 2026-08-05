import os
from unittest.mock import patch
from app.agent import get_available_provider_configs, get_llm_client_config, TrendlyAgent


def test_openai_priority():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-test-openai",
        "GROQ_API_KEY": "gsk_test_groq",
        "GEMINI_API_KEY": "gemini_test_key"
    }, clear=True):
        configs = get_available_provider_configs()
        assert len(configs) == 3
        assert configs[0]["provider"] == "openai"
        assert configs[0]["api_key"] == "sk-test-openai"
        assert configs[0]["model"] == "gpt-4o-mini"
        assert configs[1]["provider"] == "groq"
        assert configs[2]["provider"] == "gemini"


def test_groq_fallback_when_openai_missing():
    with patch.dict(os.environ, {
        "GROQ_API_KEY": "gsk_test_groq",
        "GEMINI_API_KEY": "gemini_test_key"
    }, clear=True):
        configs = get_available_provider_configs()
        assert len(configs) == 2
        assert configs[0]["provider"] == "groq"
        assert configs[0]["api_key"] == "gsk_test_groq"
        assert configs[0]["model"] == "llama-3.3-70b-versatile"
        assert configs[1]["provider"] == "gemini"


def test_gemini_fallback_when_others_missing():
    with patch.dict(os.environ, {
        "GEMINI_API_KEY": "gemini_test_key"
    }, clear=True):
        configs = get_available_provider_configs()
        assert len(configs) == 1
        assert configs[0]["provider"] == "gemini"
        assert configs[0]["api_key"] == "gemini_test_key"
        assert configs[0]["model"] == "gemini-2.5-flash"


def test_explicit_api_key_override():
    config = get_llm_client_config(api_key="sk-explicit-openai")
    assert config["provider"] == "openai"
    assert config["api_key"] == "sk-explicit-openai"
