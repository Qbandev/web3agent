<h1 align="center">
  <br>
  <code>⟨ WEB3AGENT ⟩</code>
  <br>
</h1>

<p align="center">
  <strong>AI-powered blockchain assistant with real-time crypto data</strong>
</p>

<p align="center">
  <a href="https://github.com/Qbandev/web3agent/actions/workflows/ci.yml">
    <img src="https://github.com/Qbandev/web3agent/actions/workflows/ci.yml/badge.svg" alt="CI">
  </a>
  <a href="https://github.com/Qbandev/web3agent/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
  </a>
  <img src="https://img.shields.io/badge/python-3.12+-green.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/MCP-3_servers-purple.svg" alt="MCP Servers">
</p>

<p align="center">
  <img src="docs/images/web3agent.png" alt="Web3Agent Screenshot" width="800">
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔗 **Multi-Server MCP** | Connects to 3 blockchain data providers simultaneously |
| 🤖 **Groq LLM** | Fast inference with `openai/gpt-oss-20b` model |
| 💰 **Real-time Prices** | Live crypto prices via CoinGecko |
| 👛 **Wallet Analytics** | Balance & transaction history via Hive Intelligence |
| 📅 **Web3 Events** | Discover conferences & events via GoWeb3 |
| 🎨 **Cyberpunk UI** | Sleek dark theme with neon accents |

## 🖥️ MCP Servers

| Server | Capabilities |
|--------|--------------|
| **CoinGecko** | Crypto prices, market caps, trending coins |
| **Hive Intelligence** | Wallet balances, transaction history, DeFi analytics |
| **GoWeb3** | Web3 events and conferences |

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [Groq API Key](https://console.groq.com/) (free tier available)

### Local Development

```bash
# Clone
git clone https://github.com/Qbandev/web3agent.git
cd web3agent

# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
export GROQ_API_KEY="your_groq_api_key"

# Run
streamlit run src/web3agent/app.py
```

### 🐳 Docker

```bash
docker build -t web3agent .
docker run -p 8501:8501 -e GROQ_API_KEY="your_key" web3agent
```

Open [http://localhost:8501](http://localhost:8501)

## 💬 Example Queries

```
What is the current price of Ethereum?
```
```
Show me the top 5 trending coins
```
```
What's the total balance in wallet 0xcF26040D93a6267741a2DD2cC5E1A3253dD868Ab?
```
```
Show transaction history for 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|:--------:|
| `GROQ_API_KEY` | Groq API key for LLM inference | ✅ |

### MCP Servers

Servers are configured in `mcp_agent.config.yaml`:

```yaml
mcp:
  servers:
    coingecko:
      transport: streamable_http
      url: "https://mcp.api.coingecko.com/mcp"
    hive:
      transport: streamable_http
      url: "https://mcp.hiveintelligence.xyz/mcp"
    goweb3:
      transport: streamable_http
      url: "https://goweb3-mcp-server.onrender.com/mcp"
```

## 🧪 Development

```bash
# Run tests
pytest tests/ -v

# Lint & format
ruff check src/ tests/
ruff format src/ tests/

# Security scan
bandit -r src/ -ll
```

## 📁 Project Structure

```
web3agent/
├── src/web3agent/
│   ├── app.py           # Streamlit entry point
│   ├── mcp_client.py    # MCP server connections
│   ├── agent.py         # Server configuration
│   └── ui/chat.py       # Chat components
├── tests/               # Test suite
├── docs/images/         # Screenshots
└── Dockerfile           # Container config
```

## 🌐 Deployment

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

The app is configured for Render deployment via `render.yaml`.

## 📄 License

MIT © [Qbandev](https://github.com/Qbandev)

---

<p align="center">
  Built with 💜 using <a href="https://github.com/lastmile-ai/mcp-agent">mcp-agent</a> • <a href="https://groq.com">Groq</a> • <a href="https://streamlit.io">Streamlit</a>
</p>
