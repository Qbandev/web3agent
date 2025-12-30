"""MCP Client for Web3Agent following mcp-agent best practices.

References:
- https://github.com/lastmile-ai/mcp-agent
- https://docs.mcp-agent.com
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Security: Maximum response size to prevent memory exhaustion
MAX_RESPONSE_SIZE = 100000  # 100KB


@dataclass
class Tool:
    """MCP Tool definition with type-safe parameter handling."""

    name: str
    description: str
    parameters: dict[str, Any]
    server: str

    # Parameter type hints for common tools (prevents LLM type errors)
    TYPE_HINTS: dict[str, dict[str, type]] = field(
        default_factory=lambda: {
            "coingecko_get_coins_markets": {"page": int, "per_page": int, "sparkline": bool},
            "coingecko_get_simple_price": {"include_market_cap": bool, "include_24hr_vol": bool},
            "etherscan_balanceERC20": {"chainid": int, "page": int, "offset": int},
            "etherscan_balanceNative": {"chainid": int},
            "etherscan_normalTxsByAddress": {"chainid": int, "page": int, "offset": int},
            "goweb3_search_events_by_month": {"limit": int},
            "goweb3_search_events_by_region": {"limit": int},
        },
        repr=False,
    )

    def to_groq_function(self) -> dict[str, Any]:
        """Convert to Groq function format with type hints in description."""
        # Add type hints to description to help LLM
        type_hints = self.TYPE_HINTS.get(self.name, {})
        hint_text = ""
        if type_hints:
            hints = [f"{k}={t.__name__}" for k, t in type_hints.items()]
            hint_text = f" Types: {', '.join(hints)}"

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": f"[{self.server}] {self.description}{hint_text}",
                "parameters": self.parameters,
            },
        }

    def coerce_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Coerce argument types based on known schemas."""
        type_hints = self.TYPE_HINTS.get(self.name, {})
        result = dict(args)

        for key, expected_type in type_hints.items():
            if key in result:
                val = result[key]
                try:
                    if expected_type is int and isinstance(val, str):
                        result[key] = int(val)
                    elif expected_type is bool and isinstance(val, str):
                        result[key] = val.lower() in ("true", "1", "yes")
                except (ValueError, TypeError):
                    pass

        return result


class MCPClient:
    """Manages MCP server connections and tool execution.

    Reads configuration from mcp_agent.config.yaml - no hardcoded values.
    """

    def __init__(self):
        self.tools: list[Tool] = []
        self._connected = False
        self._aggregator = None
        self._app_ctx = None
        self._server_configs: dict[str, dict[str, Any]] = {}  # Loaded from config

    @property
    def connected(self) -> bool:
        return self._connected

    def _load_server_configs(self, app) -> dict[str, dict[str, Any]]:
        """Load server configurations from mcp_agent.config.yaml."""
        configs = {}
        try:
            settings = app.context.config if hasattr(app, "context") else None
            if settings and hasattr(settings, "mcp") and settings.mcp:
                for name, server in settings.mcp.servers.items():
                    url = getattr(server, "url", None)
                    headers = getattr(server, "headers", {}) or {}
                    # Expand environment variables in headers
                    expanded_headers = {}
                    for k, v in headers.items():
                        if isinstance(v, str) and v.startswith("Bearer ${"):
                            env_var = v.replace("Bearer ${", "").replace("}", "")
                            expanded_headers[k] = f"Bearer {os.getenv(env_var, '')}"
                        else:
                            expanded_headers[k] = v
                    configs[name] = {"url": url, "headers": expanded_headers}
                    logger.info(f"Loaded config for {name}: {url}")
        except Exception as e:
            logger.warning(f"Could not load server configs: {e}")
        return configs

    async def connect(self) -> list[Tool]:
        """Connect to ALL MCP servers at once and discover tools.

        Uses MCPAggregator to connect to all servers in a single call.
        mcp-agent handles individual server failures gracefully.
        """
        from mcp_agent.app import MCPApp
        from mcp_agent.mcp.mcp_aggregator import MCPAggregator

        logger.info("Connecting to MCP servers...")

        try:
            app = MCPApp(name="web3agent")
            self._app_ctx = app.run()
            await self._app_ctx.__aenter__()

            # Load server configs from mcp_agent.config.yaml
            self._server_configs = self._load_server_configs(app)
            servers = list(self._server_configs.keys())

            if not servers:
                raise Exception("No MCP servers configured")

            # Connect ALL servers at once - mcp-agent handles failures
            logger.info(f"Connecting to all servers: {servers}")
            self._aggregator = await asyncio.wait_for(
                MCPAggregator.create(
                    server_names=servers,
                    connection_persistence=True,
                ),
                timeout=90.0,  # Allow time for all servers
            )

            # Discover tools from connected servers
            tools_result = await asyncio.wait_for(self._aggregator.list_tools(), timeout=30.0)

            raw_tools = getattr(tools_result, "tools", tools_result) or []
            if not isinstance(raw_tools, list):
                raw_tools = list(raw_tools) if raw_tools else []

            logger.info(f"Discovered {len(raw_tools)} tools from MCP servers")

            # Parse tools into our format
            self.tools = []
            for t in raw_tools:
                name = getattr(t, "name", None)
                if name is None and isinstance(t, dict):
                    name = t.get("name")
                if not name:
                    continue

                desc = getattr(t, "description", "") or ""
                params = getattr(t, "inputSchema", None)

                # Determine server from tool name prefix
                server = "mcp"
                for server_name in self._server_configs:
                    if name.startswith(f"{server_name}_"):
                        server = server_name
                        break

                if not params or not isinstance(params, dict):
                    params = {"type": "object", "properties": {}, "required": []}

                self.tools.append(
                    Tool(
                        name=name,
                        description=desc or f"Tool from {server}",
                        parameters=params,
                        server=server,
                    )
                )

            self._connected = True
            logger.info(f"Ready! {len(self.tools)} tools available")
            return self.tools

        except TimeoutError:
            logger.error("Connection timed out after 90s")
            self._connected = False
            raise Exception("MCP server connection timed out") from None
        except Exception as e:
            logger.error(f"Connection failed: {e}", exc_info=True)
            self._connected = False
            raise

    async def disconnect(self):
        """Disconnect from MCP servers."""
        if self._aggregator:
            try:
                await self._aggregator.close()
            except Exception as e:
                logger.debug(f"Error closing aggregator: {e}")
            self._aggregator = None

        if self._app_ctx:
            try:
                await self._app_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Error closing app context: {e}")
            self._app_ctx = None

        self._connected = False

    def get_tool_names(self, servers: list[str] | None = None) -> list[str]:
        """Get tool names with descriptions for tool selection.

        Args:
            servers: List of server names to filter by.

        Returns:
            List of "name: description" strings.
        """
        filtered = [t for t in self.tools if t.server in servers] if servers else self.tools
        return [f"{t.name}: {t.description[:100]}" for t in filtered]

    def get_single_tool(self, tool_name: str) -> dict[str, Any] | None:
        """Get a single tool definition by name.

        Args:
            tool_name: Name of the tool to get.

        Returns:
            Tool in Groq function format, or None if not found.
        """
        for t in self.tools:
            if t.name == tool_name:
                return t.to_groq_function()
        return None

    def find_closest_tool(self, tool_name: str) -> str | None:
        """Find the closest matching tool name (handles LLM hallucinations).

        Args:
            tool_name: The tool name from LLM (may be incorrect).

        Returns:
            The actual tool name if found/matched, or None.
        """
        # Exact match
        tool_names = [t.name for t in self.tools]
        if tool_name in tool_names:
            return tool_name

        # Try common fixes: singular/plural
        if tool_name.endswith("s"):
            singular = tool_name[:-1]
            if singular in tool_names:
                logger.warning(f"Tool name corrected: {tool_name} → {singular}")
                return singular
        else:
            plural = tool_name + "s"
            if plural in tool_names:
                logger.warning(f"Tool name corrected: {tool_name} → {plural}")
                return plural

        # Try prefix match (same server, similar name)
        for actual_name in tool_names:
            # Check if they share a prefix and are very similar (1-2 chars diff)
            shares_prefix = tool_name.startswith(actual_name[:20]) or actual_name.startswith(
                tool_name[:20]
            )
            similar_length = abs(len(tool_name) - len(actual_name)) <= 2
            if shares_prefix and similar_length:
                logger.warning(f"Tool name corrected: {tool_name} → {actual_name}")
                return actual_name

        logger.error(f"Tool not found and no close match: {tool_name}")
        return None

    def get_groq_tools(self, servers: list[str] | None = None) -> list[dict[str, Any]]:
        """Get all tools in Groq function format, filtered by server.

        Args:
            servers: List of server names to filter by.

        Returns:
            List of tools in Groq function format.
        """
        filtered = [t for t in self.tools if t.server in servers] if servers else self.tools
        return [t.to_groq_function() for t in filtered]

    def get_tools_by_server(self) -> dict[str, list[str]]:
        """Get tool names grouped by server."""
        result: dict[str, list[str]] = {}
        for tool in self.tools:
            result.setdefault(tool.server, []).append(tool.name)
        return result

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute an MCP tool with type coercion.

        Args:
            name: Tool name (with server prefix like etherscan_balanceNative).
            arguments: Tool arguments.

        Returns:
            Tool result as string.
        """
        # Find tool and coerce argument types
        tool = next((t for t in self.tools if t.name == name), None)
        if tool:
            arguments = tool.coerce_args(arguments)

        # Log tool call without exposing full arguments (security)
        logger.info(f"Calling tool: {name} with {len(arguments)} args")

        # Extract server from tool name prefix
        server = None
        tool_name = name
        for prefix in self._server_configs:
            if name.startswith(f"{prefix}_"):
                server = prefix
                tool_name = name[len(prefix) + 1 :]
                break

        # Fallback: try first part before underscore
        if not server and "_" in name:
            parts = name.split("_", 1)
            server = parts[0]
            tool_name = parts[1]

        # Get config from loaded configs (from mcp_agent.config.yaml)
        config = self._server_configs.get(server)
        if not config or not config.get("url"):
            return json.dumps({"error": f"Unknown server: {server}"})

        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **config["headers"],
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Initialize session
                init_data = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "web3agent", "version": "1.0"},
                    },
                    "id": 1,
                }

                r1 = await client.post(config["url"], json=init_data, headers=headers)
                session_id = r1.headers.get("mcp-session-id")
                if session_id:
                    headers["mcp-session-id"] = session_id

                # Call tool
                call_data = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                    "id": 2,
                }

                r2 = await client.post(config["url"], json=call_data, headers=headers)
                logger.info(f"Tool response status: {r2.status_code}")

                # Parse SSE response with validation
                text = r2.text[:MAX_RESPONSE_SIZE]

                if "data:" in text:
                    # Extract JSON from SSE format
                    match = re.search(r"data:\s*(\{.*\})", text, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            if not isinstance(data, dict):
                                return json.dumps({"error": "Invalid response format"})
                            if "result" in data and "content" in data["result"]:
                                content = data["result"]["content"]
                                if isinstance(content, list) and content:
                                    return str(content[0].get("text", str(content[0])))[
                                        :MAX_RESPONSE_SIZE
                                    ]
                                return str(content)[:MAX_RESPONSE_SIZE]
                            if "error" in data:
                                return json.dumps(data["error"])
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON in tool response")
                            return json.dumps({"error": "Invalid response format"})

                return text

        except TimeoutError:
            logger.error(f"Tool call timed out: {name}")
            return json.dumps({"error": "Tool call timed out after 30s"})
        except Exception as e:
            logger.error(f"Tool call failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})


# Global client
mcp_client = MCPClient()
