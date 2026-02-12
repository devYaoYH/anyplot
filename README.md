# AnyPlot

A local-first, privacy-preserving data visualization platform. AnyPlot enables users to create visualizations from sensitive datasets using Claude without exposing raw data to the LLM.

## How It Works

```
CSV Upload → Local SQL Filtering → Privacy Layer → Claude → Code Execution → Visualization
```

1. **Data stays local**: CSVs are parsed and queried entirely in-browser (SQLite WASM)
2. **Privacy firewall**: Claude only sees masked column names and differentially private statistics
3. **Safe execution**: Generated visualization code runs in a sandboxed subprocess

## Project Structure

```
anyplot/
├── mcp/        # Sanctum privacy layer (DP engine, schema masking, MCP protocol)
├── server/     # FastAPI backend (agent orchestration, sandbox execution)
├── app/        # React frontend (data upload, SQL editor, visualization)
└── tests/      # End-to-end tests
```

## Quick Start

```bash
# Prerequisites: Python 3.12+, Node.js 20+, uv

# Setup backend
uv venv && uv pip install -e ./server -e ./mcp

# Setup frontend
cd app && npm install && cd ..

# Run (two terminals)
uv run uvicorn server.src.main:app --reload --port 8000
cd app && npm run dev
```

## Testing

```bash
# Unit tests (fast, no API)
uv run pytest mcp/tests/unit server/tests/unit
cd app && npm run test:unit

# E2E tests (requires API key)
ANTHROPIC_API_KEY=sk-... uv run pytest tests/
```

## Documentation

- [DESIGN.md](./DESIGN.md) - System architecture and security model
- [IMPLEMENTATION.md](./IMPLEMENTATION.md) - Implementation guide for developers
