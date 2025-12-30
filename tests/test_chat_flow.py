"""Integration tests for the chat flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestStreamResponse:
    """Integration tests for the stream_response function."""

    @pytest.fixture
    def mock_groq_client(self):
        """Create a mock Groq client."""
        mock = MagicMock()
        return mock

    @pytest.fixture
    def mock_mcp_client(self):
        """Create a mock MCP client."""
        mock = MagicMock()
        mock.connected = True
        mock.get_groq_tools.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "coingecko_get_simple_price",
                    "description": "Get price for a coin",
                    "parameters": {
                        "type": "object",
                        "properties": {"ids": {"type": "string"}},
                        "required": ["ids"],
                    },
                },
            }
        ]
        return mock

    def test_stream_response_without_tools(self, mock_groq_client, mock_mcp_client):
        """Test response generation when no tool calls are made."""
        # Setup mock response without tool calls
        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "Bitcoin is a cryptocurrency."

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_groq_client.chat.completions.create.return_value = mock_response

        with (
            patch("web3agent.app.get_groq_client", return_value=mock_groq_client),
            patch("web3agent.app.mcp_client", mock_mcp_client),
        ):
            from web3agent.app import stream_response

            result = list(stream_response("What is Bitcoin?", []))

            assert len(result) > 0
            assert "Bitcoin is a cryptocurrency." in "".join(result)

    def test_stream_response_rate_limit(self, mock_groq_client, mock_mcp_client):
        """Test rate limit handling."""
        mock_groq_client.chat.completions.create.side_effect = Exception("429 rate_limit_exceeded")

        with (
            patch("web3agent.app.get_groq_client", return_value=mock_groq_client),
            patch("web3agent.app.mcp_client", mock_mcp_client),
        ):
            from web3agent.app import stream_response

            result = list(stream_response("Test query", []))

            full_response = "".join(result)
            assert "Rate limit" in full_response


class TestMCPClientIntegration:
    """Integration tests for MCPClient."""

    def test_get_groq_tools_format(self):
        """Test that tools are formatted correctly for Groq."""
        from web3agent.mcp_client import MCPClient, Tool

        client = MCPClient()
        client.tools = [
            Tool(
                name="test_tool",
                description="Test description",
                parameters={"type": "object", "properties": {}},
                server="test",
            )
        ]

        tools = client.get_groq_tools()

        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "test_tool"

    def test_get_groq_tools_filter_by_server(self):
        """Test filtering tools by server."""
        from web3agent.mcp_client import MCPClient, Tool

        client = MCPClient()
        client.tools = [
            Tool(name="coingecko_price", description="Price", parameters={}, server="coingecko"),
            Tool(
                name="etherscan_balance", description="Balance", parameters={}, server="etherscan"
            ),
        ]

        coingecko_tools = client.get_groq_tools(servers=["coingecko"])

        assert len(coingecko_tools) == 1
        assert "coingecko_price" in coingecko_tools[0]["function"]["name"]

    def test_get_tools_by_server(self):
        """Test grouping tools by server."""
        from web3agent.mcp_client import MCPClient, Tool

        client = MCPClient()
        client.tools = [
            Tool(name="coingecko_a", description="A", parameters={}, server="coingecko"),
            Tool(name="coingecko_b", description="B", parameters={}, server="coingecko"),
            Tool(name="etherscan_c", description="C", parameters={}, server="etherscan"),
        ]

        by_server = client.get_tools_by_server()

        assert len(by_server["coingecko"]) == 2
        assert len(by_server["etherscan"]) == 1


class TestChatHistory:
    """Tests for chat history using MagicMock for Streamlit session_state."""

    def test_add_user_message(self):
        """Test adding user messages to history."""
        with patch("web3agent.ui.chat.st") as mock_st:
            # MagicMock allows attribute access like real session_state
            mock_st.session_state.messages = []

            from web3agent.ui.chat import add_user_message

            add_user_message("Hello")

            assert len(mock_st.session_state.messages) == 1
            assert mock_st.session_state.messages[0]["role"] == "user"
            assert mock_st.session_state.messages[0]["content"] == "Hello"

    def test_add_assistant_message(self):
        """Test adding assistant messages to history."""
        with patch("web3agent.ui.chat.st") as mock_st:
            mock_st.session_state.messages = []

            from web3agent.ui.chat import add_assistant_message

            add_assistant_message("Hi there!")

            assert len(mock_st.session_state.messages) == 1
            assert mock_st.session_state.messages[0]["role"] == "assistant"
            assert mock_st.session_state.messages[0]["content"] == "Hi there!"
