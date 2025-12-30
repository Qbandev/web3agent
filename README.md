# Web3Agent

AI assistant powered by MCP servers for blockchain and crypto capabilities.

## Features

- **Multi-Server MCP Integration**: Connects to 3 external MCP servers
  - Hive Intelligence (Crypto analytics, wallet balances)
  - CoinGecko (Price data, trending coins)
  - GoWeb3 (Web3 events)
- **Groq LLM**: Uses `openai/gpt-oss-20b` model via Groq API
- **Streamlit UI**: Cyberpunk-themed chat interface with streaming responses
- **Docker Ready**: Optimized for deployment

## Quick Start

### Prerequisites

- Python 3.12+
- [Groq API Key](https://console.groq.com/)

### Local Development

```bash
# Clone the repository
git clone https://github.com/Qbandev/web3agent.git
cd web3agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GROQ_API_KEY="your_groq_api_key"

# Run the app
streamlit run src/web3agent/app.py
```

### Docker

```bash
# Build and run
docker build -t web3agent .
docker run -p 8501:8501 \
  -e GROQ_API_KEY="your_groq_api_key" \
  web3agent
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq API key for LLM | Yes |

### MCP Servers

Configure servers in `mcp_agent.config.yaml`:

```yaml
mcp:
  servers:
    coingecko:
      transport: streamable_http
      url: "https://mcp.api.coingecko.com/mcp"
```

## Development

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

## License

MIT

