"""Chat UI components for Web3Agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from collections.abc import Generator


def init_session_state() -> None:
    """Initialize Streamlit session state for chat."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "tool_calls" not in st.session_state:
        st.session_state.tool_calls = []


def render_chat_history() -> None:
    """Render all messages in chat history."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def add_user_message(content: str) -> None:
    """Add a user message to chat history."""
    st.session_state.messages.append({"role": "user", "content": content})


def add_assistant_message(content: str) -> None:
    """Add an assistant message to chat history."""
    st.session_state.messages.append({"role": "assistant", "content": content})


def render_sidebar() -> None:
    """Render the sidebar with server status and configuration."""
    with st.sidebar:
        st.markdown("### MCP SERVERS")
        st.markdown("---")

        connected = st.session_state.get("mcp_connected", False)
        status_icon = "◉" if connected else "◯"
        status_color = "#00ff9f" if connected else "#ff0066"

        servers = [
            ("COINGECKO", "Crypto prices, market caps, trending coins"),
            ("HIVE", "Wallet balances, transactions, DeFi analytics"),
            ("GOWEB3", "Web3 events and conferences"),
        ]

        for name, description in servers:
            st.markdown(
                f'<span style="color: {status_color}; font-family: Share Tech Mono;">'
                f"{status_icon}</span> "
                f'<span style="color: #ff00ff; font-family: Orbitron; font-size: 0.85em;">'
                f"{name}</span><br/>"
                f'<span style="color: #888; font-family: Share Tech Mono; font-size: 0.7em; '
                f'padding-left: 1.2em; display: block; margin-top: 2px;">'
                f"{description}</span>",
                unsafe_allow_html=True,
            )
            st.markdown("")

        st.markdown("---")
        st.markdown("### SYSTEM")

        tool_count = len(st.session_state.get("mcp_tools", []))
        status_text = "ONLINE" if connected else "OFFLINE"

        st.markdown(
            f'<span style="color: #666699; font-family: Share Tech Mono; font-size: 0.8em;">'
            f"◈ MODEL: gpt-oss-20b<br/>"
            f"◈ PROVIDER: GROQ.CORP<br/>"
            f"◈ STATUS: {status_text}<br/>"
            f"◈ TOOLS: {tool_count}"
            f"</span>",
            unsafe_allow_html=True,
        )

        st.markdown("---")

        if st.button("⌫ PURGE MEMORY"):
            st.session_state.messages = []
            st.rerun()


def stream_wrapper(async_gen) -> Generator[str, None, None]:
    """Wrap async generator for Streamlit's write_stream.

    Args:
        async_gen: Async generator yielding string chunks.

    Yields:
        String chunks for Streamlit rendering.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        while True:
            try:
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
            except StopAsyncIteration:
                break
    finally:
        loop.close()
