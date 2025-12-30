"""Web3Agent Streamlit Application."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import streamlit as st
from groq import Groq

from web3agent.mcp_client import mcp_client
from web3agent.ui.chat import (
    add_assistant_message,
    add_user_message,
    init_session_state,
    render_chat_history,
    render_sidebar,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Web3Agent",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_css() -> str:
    """Load CSS from external file."""
    css_path = Path(__file__).parent / "static" / "cyberpunk.css"
    if css_path.exists():
        return css_path.read_text()
    return ""


# Cyberpunk CSS theme (loaded from static/cyberpunk.css)
st.markdown(
    f"<style>{load_css()}</style>",
    unsafe_allow_html=True,
)

# LLM model from environment or default
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create event loop for async operations."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def init_mcp_connection():
    """Initialize MCP server connections on startup."""
    if st.session_state.get("mcp_connected") or st.session_state.get("mcp_connecting"):
        return

    st.session_state.mcp_connecting = True
    try:
        loop = get_event_loop()
        tools = loop.run_until_complete(mcp_client.connect())
        st.session_state.mcp_connected = True
        st.session_state.mcp_tools = [t.name for t in tools]
        st.session_state.mcp_connecting = False
        logger.info(f"MCP connected with {len(tools)} tools")
    except Exception as e:
        logger.error(f"MCP connection failed: {e}", exc_info=True)
        st.session_state.mcp_connected = False
        st.session_state.mcp_connecting = False
        st.session_state.mcp_error = str(e)


def get_groq_client() -> Groq:
    """Get Groq client."""
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("Please set GROQ_API_KEY environment variable")
        st.stop()
    return Groq(api_key=api_key)


def stream_response(prompt: str, history: list[dict]):
    """Stream response using native Groq function calling.

    Flow:
    1. Pass ALL discovered MCP tools to Groq via native function calling
    2. Groq selects and calls appropriate tool(s)
    3. Execute tool calls and return results
    4. Generate final response

    Args:
        prompt: User's input message.
        history: Chat history.

    Yields:
        Response chunks for st.write_stream().
    """
    client = get_groq_client()

    if not mcp_client.connected:
        yield "⚠️ MCP servers not connected. Attempting to connect...\n\n"
        init_mcp_connection()
        if not mcp_client.connected:
            yield f"❌ Failed to connect: {st.session_state.get('mcp_error', 'Unknown error')}\n"
            return

    # Get ALL tools from MCP servers (discovered programmatically)
    groq_tools = mcp_client.get_groq_tools()
    logger.info(f"Passing {len(groq_tools)} tools to LLM")

    # Get dynamic server context for better tool selection
    server_context = mcp_client.get_server_context_for_llm()

    # System prompt with dynamic server capabilities
    system_prompt = f"""You are Web3Agent, an AI assistant specializing in blockchain and cryptocurrency data.

## CAPABILITIES
You can retrieve: crypto prices, market data, trending coins, wallet balances, Web3 events, and analytics.
You CANNOT: execute transactions, provide financial advice, or predict prices.

{server_context}

## TOOL SELECTION
1. Match user intent to the appropriate server based on capabilities above.
2. Tool names include server prefix and category: [ServerName|Category] in descriptions.
3. For simple questions (greetings, explanations), respond without tools.
4. For data requests, ALWAYS use tools from the appropriate server.

## TOOL CALLING RULES
- Only call tools EXACTLY as named in your tools list. Never guess or modify names.
- Provide valid JSON arguments. Use {{}} (empty object) for tools with no required params.
- Read tool descriptions carefully - they include parameter types.

## HIVE INTELLIGENCE PATTERN (MANDATORY 3-STEP WORKFLOW)
Hive requires THREE steps - YOU MUST COMPLETE ALL THREE:
1. `hive_get_*_endpoints` → Discovery (NO params, use {{}})
2. `hive_get_api_endpoint_schema` → Get params (pass {{"name": "endpoint_name"}})
3. `hive_invoke_api_endpoint` → Execute with {{"endpoint_name": "...", "args": {{...}}}}

EXAMPLE for wallet balance:
1. `hive_get_portfolio_wallet_endpoints` with {{}}
2. `hive_get_api_endpoint_schema` with {{"name": "user_total_balance"}}
3. `hive_invoke_api_endpoint` with {{"endpoint_name": "user_total_balance", "args": {{"id": "0x..."}}}}

EXAMPLE for transaction history:
1. `hive_get_portfolio_wallet_endpoints` with {{}}
2. `hive_get_api_endpoint_schema` with {{"name": "user_history"}}
3. `hive_invoke_api_endpoint` with {{"endpoint_name": "user_history", "args": {{"id": "0x..."}}}}

⚠️ CRITICAL RULES:
- NEVER stop after step 1 or 2. ALWAYS complete step 3 to get actual data.
- NEVER explain what you "would do" - actually DO IT.
- Use "endpoint_name" and "args" for hive_invoke_api_endpoint (NOT "name" and "params").
- Your response should contain REAL DATA from the API, not descriptions of tools.

## ERROR HANDLING
- If a tool fails, check schema and RETRY with correct params
- Never fabricate data

## OUTPUT FORMAT
- Present ACTUAL DATA returned by tools, not tool descriptions
- Use tables for structured data (balances, transactions)
- Be concise - users want data, not explanations"""

    # Build message history
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-5:]:  # Keep last 5 messages for context
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

    tool_results = []
    max_iterations = 5  # Allow more iterations for discover → try → learn → retry patterns

    for _iteration in range(max_iterations):
        try:
            # Call Groq with ALL discovered tools - let model decide
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=groq_tools if groq_tools else None,
                tool_choice="auto" if groq_tools else None,
                max_tokens=2048,
            )
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str:
                yield "\n⚠️ **Rate limit reached.** Try again in a few minutes.\n"
                return
            if "413" in error_str or "too large" in error_str.lower():
                yield "\n⚠️ **Request too large.** Trying with fewer tools...\n"
                groq_tools = mcp_client.get_groq_tools(servers=["coingecko"])
                continue
            if "Failed to parse tool call arguments as JSON" in error_str:
                logger.warning(f"LLM generated malformed JSON, retrying: {e}")
                continue
            if "output_parse_failed" in error_str or "could not be parsed" in error_str:
                logger.warning(f"LLM output parsing failed, retrying: {e}")
                continue
            if "not in request.tools" in error_str or "tool_use_failed" in error_str:
                import re

                # Different feedback based on error type
                if "parameters for tool" in error_str and "did not match schema" in error_str:
                    # LLM passed wrong params to a tool
                    tool_match = re.search(r"parameters for tool (\S+)", error_str)
                    bad_tool = tool_match.group(1) if tool_match else "unknown"
                    logger.warning(f"LLM passed wrong params to '{bad_tool}': {e}")

                    feedback = (
                        f"ERROR: You passed wrong parameters to '{bad_tool}'. "
                        "Remember: hive_get_*_endpoints tools take NO parameters (use {{}}). "
                        "For hive_invoke_api_endpoint, use: "
                        '{{"endpoint_name": "user_history", "args": {{"id": "0x..."}}}}. '
                        "Note: use 'endpoint_name' and 'args', NOT 'name' and 'params'."
                    )
                    messages.append(
                        {"role": "assistant", "content": f"I called {bad_tool} with wrong params"}
                    )
                    messages.append({"role": "user", "content": feedback})
                    # Don't show internal error correction to user - just retry silently
                else:
                    # LLM tried to call a non-existent tool
                    bad_tool_match = re.search(r"tool '([^']+)'", error_str)
                    bad_tool = bad_tool_match.group(1) if bad_tool_match else "unknown"
                    logger.warning(f"LLM hallucinated tool name '{bad_tool}': {e}")

                    feedback = (
                        f"ERROR: '{bad_tool}' is NOT a valid tool. "
                        "Endpoint names like 'user_total_balance' are NOT tools. "
                        'Use hive_invoke_api_endpoint with {{"name": "user_total_balance", "params": {{...}}}}.'
                    )
                    messages.append({"role": "assistant", "content": f"I tried to call {bad_tool}"})
                    messages.append({"role": "user", "content": feedback})
                    # Don't show internal error correction to user - just retry silently
                continue
            logger.error(f"Groq API error: {e}", exc_info=True)
            yield "\n❌ An error occurred. Please try again.\n"
            return

        message = response.choices[0].message

        # Check if model wants to call tools
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_name = tc.function.name
                try:
                    func_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    func_args = {}

                # Fix hallucinated tool names (e.g., singular vs plural)
                corrected_name = mcp_client.find_closest_tool(tool_name)
                if not corrected_name:
                    logger.warning(f"Tool `{tool_name}` not found, skipping")
                    continue
                if corrected_name != tool_name:
                    logger.info(f"Corrected tool name: {tool_name} -> {corrected_name}")
                    tool_name = corrected_name

                # Show clean tool execution indicator
                short_name = tool_name.split("_", 1)[-1].replace("_", " ").title()
                yield f"\n▸ {short_name}..."

                logger.info(f"Tool call: {tool_name} with {len(func_args)} args")

                # Execute tool via MCP client
                loop = get_event_loop()
                result = loop.run_until_complete(mcp_client.call_tool(tool_name, func_args))
                yield " ✓"

                # Update sidebar with tool output
                st.session_state.tool_output = result[:500]

                tool_results.append({"tool": tool_name, "args": func_args, "result": result})

                # Add tool result to messages for next iteration
                messages.append(
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tool_name, "arguments": tc.function.arguments},
                            }
                        ],
                    }
                )
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        else:
            # No more tool calls - model has final answer
            if message.content:
                yield message.content
            return

    # After iterations, generate final response based on tool results
    if tool_results:
        yield "\n\n📊 **Results:**\n\n"

        # Get the last invoke result (actual data), or last result if no invoke
        invoke_results = [r for r in tool_results if "invoke" in r.get("tool", "")]
        data_to_show = invoke_results[-1] if invoke_results else tool_results[-1]

        # Ask model to summarize just the actual data
        summary_messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant. Present data clearly using tables or bullet points. Be concise.",
            },
            {
                "role": "user",
                "content": f"The user asked: '{prompt}'\n\nHere is the data:\n{data_to_show.get('result', '')[:3000]}\n\nPresent this data clearly.",
            },
        ]

        try:
            final = client.chat.completions.create(
                model=LLM_MODEL,
                messages=summary_messages,
                stream=True,
                max_tokens=1024,
            )
            for chunk in final:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.warning(f"Failed to summarize results: {e}")
            # Show raw data as fallback
            yield f"```\n{data_to_show.get('result', 'No data')[:2000]}\n```"


def main() -> None:
    """Main Streamlit application entry point."""
    init_session_state()

    # Header
    st.markdown(
        '<h1 style="text-align: center;">WEB3AGENT</h1>',
        unsafe_allow_html=True,
    )

    # Auto-connect on startup
    if not st.session_state.get("mcp_attempted"):
        st.session_state.mcp_attempted = True
        init_mcp_connection()

    # Show error only if connection failed
    if not st.session_state.get("mcp_connected") and not st.session_state.get("mcp_connecting"):
        error = st.session_state.get("mcp_error", "")
        if error:
            st.warning(f"Connection error: {error}")

    # Sidebar
    render_sidebar()

    # Chat history
    render_chat_history()

    # Chat input
    if prompt := st.chat_input("Ask about crypto prices, wallet balances, or Web3 events..."):
        add_user_message(prompt)
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                # Show loading indicator while fetching data
                status_placeholder = st.empty()
                response_placeholder = st.empty()

                response_parts = []
                tool_count = 0

                for chunk in stream_response(prompt, st.session_state.messages[:-1]):
                    # Tool progress markers - update status
                    if chunk.startswith("\n▸ "):
                        tool_count += 1
                        tool_name = chunk.replace("\n▸ ", "").replace("...", "")
                        status_placeholder.markdown(
                            f'<div style="color: #00ff9f; font-family: Share Tech Mono; padding: 10px;">'
                            f'<span class="blinking">●</span> Fetching data... ({tool_name})'
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    elif chunk == " ✓":
                        pass  # Tool done, continue
                    else:
                        # Clear status on first content
                        if response_parts == []:
                            status_placeholder.empty()
                        response_parts.append(chunk)
                        # Update response in real-time
                        response_placeholder.markdown("".join(response_parts))

                response = "".join(response_parts)
                add_assistant_message(response)
            except Exception as e:
                error_msg = f"Something went wrong: {e!s}"
                st.error(error_msg)
                add_assistant_message(error_msg)


if __name__ == "__main__":
    main()
