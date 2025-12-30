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

    # System prompt to guide tool usage
    system_prompt = """You are a Web3 assistant with access to blockchain tools.

IMPORTANT RULES:
1. ONLY call tools from the provided tools list. Never invent tool names.
2. Some tools return lists of "endpoints" or "APIs" - these are NOT callable tools.
   When you see endpoint names like "user_total_balance" or "retrieve_topic_metrics"
   in a tool's response, you must use `hive_invoke_api_endpoint` to call them.
3. For Hive wallet queries, use this pattern:
   - Call `hive_invoke_api_endpoint` with: name="user_total_balance", params={"address": "0x...", "chain_id": 1}
4. For crypto prices, use `coingecko_*` tools directly.
5. For Web3 events, use `goweb3_*` tools directly.
6. Be concise. Present data clearly with formatting."""

    # Build message history
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-5:]:  # Keep last 5 messages for context
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

    tool_results = []
    max_iterations = 3

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
            if "tool_use_failed" in error_str or "not in request.tools" in error_str:
                # LLM hallucinated a tool name - this happens with Hive meta-tools
                logger.warning(f"LLM hallucinated tool name: {e}")
                yield "\n⚠️ That query requires a tool that isn't available. "
                yield "Try asking differently or use a more specific question.\n"
                return
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
                    yield f"⚠️ Tool `{tool_name}` not found. Skipping...\n"
                    continue
                if corrected_name != tool_name:
                    yield f"🔧 Calling `{corrected_name}` (corrected from `{tool_name}`)...\n"
                    tool_name = corrected_name
                else:
                    yield f"🔧 Calling `{tool_name}`...\n"

                logger.info(f"Tool call: {tool_name} with {len(func_args)} args")

                # Execute tool via MCP client
                loop = get_event_loop()
                result = loop.run_until_complete(mcp_client.call_tool(tool_name, func_args))

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

        # Ask model to summarize results
        summary_messages = [
            {
                "role": "user",
                "content": f"Summarize this data for the user who asked: '{prompt}'\n\nData:\n{json.dumps(tool_results, indent=2)[:3000]}",
            }
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
        except Exception:
            yield f"\n\nRaw results: {json.dumps(tool_results, indent=2)[:1000]}"


def main() -> None:
    """Main Streamlit application entry point."""
    init_session_state()

    # Header
    st.markdown(
        '<h1 style="text-align: center;">⟨ WEB3AGENT ⟩</h1>',
        unsafe_allow_html=True,
    )

    # Auto-connect on startup
    if not st.session_state.get("mcp_attempted"):
        st.session_state.mcp_attempted = True
        init_mcp_connection()

    # Status display
    if st.session_state.get("mcp_connecting"):
        st.markdown(
            '<p style="text-align: center; font-family: Share Tech Mono; color: #ffcc00;" class="blinking">'
            "// CONNECTING... //"
            "</p>",
            unsafe_allow_html=True,
        )
    elif st.session_state.get("mcp_connected"):
        tool_count = len(st.session_state.get("mcp_tools", []))
        st.markdown(
            f'<p style="text-align: center; font-family: Share Tech Mono; color: #00ff9f;">'
            f"// READY // {tool_count} TOOLS //"
            f"</p>",
            unsafe_allow_html=True,
        )
    else:
        error = st.session_state.get("mcp_error", "")
        st.markdown(
            '<p style="text-align: center; font-family: Share Tech Mono; color: #ff0066;">'
            "// OFFLINE //"
            "</p>",
            unsafe_allow_html=True,
        )
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
                response = st.write_stream(stream_response(prompt, st.session_state.messages[:-1]))
                add_assistant_message(response)
            except Exception as e:
                error_msg = f"Something went wrong: {e!s}"
                st.error(error_msg)
                add_assistant_message(error_msg)


if __name__ == "__main__":
    main()
