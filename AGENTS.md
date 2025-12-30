# Web3Agent Project Instructions

## Overview
Web3Agent is an AI assistant for blockchain and crypto queries. It connects to multiple MCP servers and uses Groq's LLM API for inference.

## Framework
- [mcp-agent](https://github.com/lastmile-ai/mcp-agent) (v0.0.21+) for MCP orchestration
- Documentation: https://docs.mcp-agent.com

## Technical Stack
- **Python 3.12+** with async/await patterns
- **Streamlit** for cyberpunk-themed chat UI
- **Groq LLM**: `openai/gpt-oss-20b` via OpenAI-compatible API
- **mcp-agent** for multi-server MCP orchestration (single connection for all servers)
- **httpx** for async HTTP calls to MCP servers

## MCP Servers
Defined in `mcp_agent.config.yaml` - **no hardcoded URLs in code**:

| Server | Transport | Description | Auth |
|--------|-----------|-------------|------|
| CoinGecko | HTTP | Price data, market caps, trending coins | None (public) |
| GoWeb3 | HTTP | Web3 events search | None |
| Hive | HTTP | Crypto market analytics, wallet balances | None |

## Configuration Files

### `mcp_agent.config.yaml`
Single source of truth for:
- MCP server URLs and headers
- LLM provider settings
- Logging configuration

### `mcp_agent.secrets.yaml` (gitignored)
Store API keys locally - **NEVER commit real keys**:
```yaml
openai:
  api_key: "${GROQ_API_KEY}"  # Use env var reference
```

## Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key for LLM |

## File Structure
```
src/web3agent/
├── __init__.py      # Package init
├── app.py           # Streamlit entry point + chat flow
├── mcp_client.py    # MCP server connections & tool execution
├── agent.py         # MCPApp configuration & server list
├── static/
│   └── cyberpunk.css  # UI theme stylesheet
└── ui/
    ├── __init__.py
    └── chat.py      # Chat UI components

tests/
├── test_connection.py    # MCP server connectivity tests
├── test_llm.py           # Groq LLM integration tests
├── test_tool_coercion.py # Tool.coerce_args() unit tests
└── test_chat_flow.py     # Chat flow integration tests
```

## Code Patterns

### MCP Connection (Single call for all servers)
```python
# Connect ALL servers at once - mcp-agent handles failures
self._aggregator = await MCPAggregator.create(
    server_names=servers,
    connection_persistence=True,
)
# Discover all tools programmatically
tools_result = await self._aggregator.list_tools()
```

### Native Function Calling
```python
# Pass ALL discovered tools to Groq - native function calling
response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=messages,
    tools=groq_tools,  # All 78 tools from MCP servers
    tool_choice="auto",
)
```

### Type Coercion
```python
# Auto-fixes LLM type errors (strings → ints/bools)
arguments = tool.coerce_args(arguments)
```

## Rate Limits

### Groq API
Check your plan limits at: https://console.groq.com/docs/rate-limits

When rate limited, wait for the reset period indicated in the error message.

## Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
streamlit run src/web3agent/app.py

# Lint
ruff check src/
```

### Docker (Recommended)
```bash
# Build
docker build -t web3agent:local .

# Run
docker run -d --name web3agent-test \
  -p 8501:8501 \
  -e GROQ_API_KEY="your-key" \
  web3agent:local

# Check health
curl http://localhost:8501/_stcore/health

# View logs
docker logs web3agent-test

# Stop
docker stop web3agent-test && docker rm web3agent-test
```

### Testing
```bash
pytest tests/ -v
```

## Security
- **NEVER** commit API keys or `mcp_agent.secrets.yaml`
- Use environment variables for all credentials
- `.gitignore` includes: `.env`, `mcp_agent.secrets.yaml`

## UI Features
- Cyberpunk theme with Orbitron/Share Tech Mono fonts
- Real-time streaming responses
- Sidebar shows MCP server status and available tools
- Tool output display panel
