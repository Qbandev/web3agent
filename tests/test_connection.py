"""Test MCP server connectivity."""

from __future__ import annotations

import pytest

from web3agent.agent import WEB3_SERVERS, app


@pytest.mark.asyncio
async def test_app_initialization():
    """Verify MCPApp initializes correctly."""
    assert app.name == "web3agent"


@pytest.mark.asyncio
async def test_servers_configured():
    """Verify all expected servers are configured."""
    expected_servers = ["hive", "coingecko", "goweb3", "etherscan"]
    assert expected_servers == WEB3_SERVERS


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires network access - run manually")
async def test_mcp_client_connection():
    """Test MCP client connects to all servers.

    This test requires network access. Run manually with:
    pytest tests/test_connection.py::test_mcp_client_connection -v --no-header
    """
    from web3agent.mcp_client import mcp_client

    tools = await mcp_client.connect()
    assert len(tools) > 0, "Should discover tools from MCP servers"
    print(f"Total tools discovered: {len(tools)}")

    # Group by server
    tools_by_server = mcp_client.get_tools_by_server()
    for server, tool_names in tools_by_server.items():
        print(f"{server}: {len(tool_names)} tools")

    await mcp_client.disconnect()
