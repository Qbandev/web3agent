"""Web3Agent - MCP Configuration with External Servers."""

from __future__ import annotations

from mcp_agent.app import MCPApp

# All configured MCP servers from mcp_agent.config.yaml
WEB3_SERVERS = ["hive", "coingecko", "goweb3", "etherscan"]

# Initialize the MCP application
app = MCPApp(name="web3agent")
