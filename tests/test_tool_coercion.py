"""Unit tests for Tool.coerce_args() type coercion."""

from __future__ import annotations

import pytest

from web3agent.mcp_client import Tool


class TestToolCoerceArgs:
    """Test cases for automatic type coercion of tool arguments."""

    @pytest.fixture
    def coingecko_tool(self) -> Tool:
        """Create a CoinGecko tool with known type hints."""
        return Tool(
            name="coingecko_get_coins_markets",
            description="Get market data for coins",
            parameters={"type": "object", "properties": {}},
            server="coingecko",
        )

    @pytest.fixture
    def hive_tool(self) -> Tool:
        """Create a Hive tool with known type hints."""
        return Tool(
            name="hive_invoke_api_endpoint",
            description="Invoke a Hive API endpoint",
            parameters={"type": "object", "properties": {}},
            server="hive",
        )

    @pytest.fixture
    def unknown_tool(self) -> Tool:
        """Create a tool without type hints."""
        return Tool(
            name="unknown_tool",
            description="Unknown tool",
            parameters={"type": "object", "properties": {}},
            server="unknown",
        )

    def test_coerce_string_to_int(self, coingecko_tool: Tool):
        """String numbers should be converted to integers."""
        args = {"page": "5", "per_page": "100"}
        result = coingecko_tool.coerce_args(args)

        assert result["page"] == 5
        assert isinstance(result["page"], int)
        assert result["per_page"] == 100
        assert isinstance(result["per_page"], int)

    def test_coerce_string_to_bool_true(self, coingecko_tool: Tool):
        """String 'true' variants should be converted to True."""
        for true_val in ["true", "True", "TRUE", "1", "yes", "YES"]:
            args = {"sparkline": true_val}
            result = coingecko_tool.coerce_args(args)

            assert result["sparkline"] is True, f"Failed for '{true_val}'"

    def test_coerce_string_to_bool_false(self, coingecko_tool: Tool):
        """String 'false' variants should be converted to False."""
        for false_val in ["false", "False", "FALSE", "0", "no", "NO"]:
            args = {"sparkline": false_val}
            result = coingecko_tool.coerce_args(args)

            assert result["sparkline"] is False, f"Failed for '{false_val}'"

    def test_preserve_already_correct_types(self, coingecko_tool: Tool):
        """Values already of correct type should not be changed."""
        args = {"page": 5, "per_page": 100, "sparkline": True}
        result = coingecko_tool.coerce_args(args)

        assert result["page"] == 5
        assert result["per_page"] == 100
        assert result["sparkline"] is True

    def test_preserve_unknown_args(self, coingecko_tool: Tool):
        """Arguments not in type hints should pass through unchanged."""
        args = {"page": "5", "unknown_arg": "some_value", "another": 123}
        result = coingecko_tool.coerce_args(args)

        assert result["page"] == 5
        assert result["unknown_arg"] == "some_value"
        assert result["another"] == 123

    def test_tool_without_hints(self, unknown_tool: Tool):
        """Tools without type hints should return args unchanged."""
        args = {"foo": "bar", "num": "123"}
        result = unknown_tool.coerce_args(args)

        assert result["foo"] == "bar"
        assert result["num"] == "123"  # Not coerced

    def test_invalid_int_string(self, coingecko_tool: Tool):
        """Invalid int strings should pass through unchanged."""
        args = {"page": "not_a_number"}
        result = coingecko_tool.coerce_args(args)

        assert result["page"] == "not_a_number"

    def test_empty_args(self, coingecko_tool: Tool):
        """Empty args dict should return empty dict."""
        result = coingecko_tool.coerce_args({})
        assert result == {}

    def test_goweb3_limit(self, unknown_tool: Tool):
        """GoWeb3 limit should be coerced to int for goweb3 tools."""
        tool = Tool(
            name="goweb3_search_events_by_month",
            description="Search events by month",
            parameters={"type": "object", "properties": {}},
            server="goweb3",
        )
        args = {"limit": "10"}
        result = tool.coerce_args(args)

        assert result["limit"] == 10
        assert isinstance(result["limit"], int)

    def test_does_not_mutate_original(self, coingecko_tool: Tool):
        """Original args dict should not be mutated."""
        original = {"page": "5"}
        result = coingecko_tool.coerce_args(original)

        assert original["page"] == "5"  # Unchanged
        assert result["page"] == 5


class TestToolToGroqFunction:
    """Test cases for converting Tool to Groq function format."""

    def test_basic_conversion(self):
        """Tool should convert to proper Groq function format."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            server="test",
        )
        result = tool.to_groq_function()

        assert result["type"] == "function"
        assert result["function"]["name"] == "test_tool"
        # New format: [ServerName|Category] description
        assert "TEST" in result["function"]["description"]
        assert "General" in result["function"]["description"]
        assert "A test tool" in result["function"]["description"]
        assert result["function"]["parameters"] == tool.parameters

    def test_includes_type_hints_in_description(self):
        """Tools with type hints should include them in description."""
        tool = Tool(
            name="coingecko_get_coins_markets",
            description="Get market data",
            parameters={"type": "object", "properties": {}},
            server="coingecko",
        )
        result = tool.to_groq_function()

        desc = result["function"]["description"]
        assert "Types:" in desc
        assert "page=int" in desc
        assert "sparkline=bool" in desc

    def test_no_type_hints_for_unknown_tool(self):
        """Unknown tools should not have type hints in description."""
        tool = Tool(
            name="some_random_tool",
            description="Random tool",
            parameters={"type": "object", "properties": {}},
            server="random",
        )
        result = tool.to_groq_function()

        desc = result["function"]["description"]
        assert "Types:" not in desc
