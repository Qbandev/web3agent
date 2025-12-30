"""Test LLM integration with Groq."""

from __future__ import annotations

import os

import pytest


@pytest.mark.asyncio
async def test_groq_api_key_configured():
    """Verify Groq API key is set in environment."""
    api_key = os.getenv("GROQ_API_KEY")
    # Skip if not configured (CI environment)
    if not api_key:
        pytest.skip("GROQ_API_KEY not set - skipping LLM test")

    assert api_key.startswith("gsk_"), "Groq API key should start with 'gsk_'"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires network access and API key - run manually")
async def test_groq_llm_response():
    """Test Groq LLM generates a response.

    This test requires:
    1. Network access
    2. GROQ_API_KEY environment variable

    Run manually with:
    GROQ_API_KEY=your_key pytest tests/test_llm.py::test_groq_llm_response -v --no-header
    """
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY not set")

    client = Groq(api_key=api_key)
    model = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hello in 5 words or less"}],
        max_tokens=50,
    )

    content = response.choices[0].message.content
    assert content and len(content) > 0, "LLM should generate a response"
    print(f"LLM response: {content}")


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires network access and API key - run manually")
async def test_groq_function_calling():
    """Test Groq LLM can use function calling.

    Run manually with:
    GROQ_API_KEY=your_key pytest tests/test_llm.py::test_groq_function_calling -v --no-header
    """
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY not set")

    client = Groq(api_key=api_key)
    model = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

    # Simple tool definition
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string", "description": "City name"}},
                    "required": ["city"],
                },
            },
        }
    ]

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "What's the weather in Paris?"}],
        tools=tools,
        tool_choice="auto",
        max_tokens=100,
    )

    message = response.choices[0].message
    assert message.tool_calls and len(message.tool_calls) > 0, "LLM should call the tool"

    tool_call = message.tool_calls[0]
    assert tool_call.function.name == "get_weather"
    print(f"Tool call: {tool_call.function.name}({tool_call.function.arguments})")
