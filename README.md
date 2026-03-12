# AnyPlot

A local-first, privacy-preserving data visualization platform. AnyPlot enables users to create visualizations from sensitive datasets using Claude without exposing raw data to the LLM.

**[Learn more](https://devyaoyh.github.io/anyplot)** | **[Documentation](./docs/)** | **[Contributing](./docs/CONTRIBUTING.md)**

## ✨ Features

- 🔒 **Privacy-First**: Differential privacy ensures no raw data leaks to the LLM
- 🏠 **Local-First**: All data processing happens on your machine
- 🤖 **AI-Powered**: Natural language prompts generate visualizations
- ⚡ **Fast**: SQLite WASM for instant local queries
- 🛡️ **Secure**: Sandboxed code execution with strict security controls
- 📊 **Flexible**: Works with any CSV data

## How It Works

```
CSV Upload → Local SQL Filtering → Privacy Layer → Claude → Code Execution → Visualization
                                         ↓
                              (Masked schema + noisy stats only)
```

1. **Data stays local**: CSVs are parsed and queried entirely in-browser (SQLite WASM)
2. **Privacy firewall**: Claude only sees masked column names and differentially private statistics
3. **Safe execution**: Generated visualization code runs in a sandboxed subprocess
4. **No data exposure**: Raw data never leaves your machine

## 🚀 Quick Start

### Prerequisites

- **Python**: 3.12 or higher
- **Node.js**: 20 or higher
- **uv**: [Install here](https://github.com/astral-sh/uv)

### Installation

```bash
# Clone repository
git clone https://github.com/devYaoYH/anyplot.git
cd anyplot

# Option 1: One-command setup (recommended)
./scripts/dev-utils.sh setup

# Option 2: Manual setup
# Backend
uv venv && uv pip install -e ./server -e ./mcp

# Frontend
cd app && npm install && cd ..
```

### Running

```bash
# Option 1: Start both servers (recommended)
./scripts/dev-utils.sh start

# Option 2: Start separately
# Terminal 1: Backend
uv run uvicorn server.src.main:app --reload --port 8000

# Terminal 2: Frontend
cd app && npm run dev
```

**Access the app**: Open [http://localhost:5173](http://localhost:5173) in your browser

### Authentication

AnyPlot supports two ways to authenticate with Claude:

- **API Key**: Set `ANTHROPIC_API_KEY` as an environment variable or enter it in the Settings panel in the UI. Calls go directly to the Anthropic API.
- **Claude Code subscription**: If you have [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and signed in (e.g., with a Pro or Max plan), AnyPlot detects it automatically — no API key needed.

**Note on packages**: Generated visualization code runs in the same Python environment as the backend server. Install additional packages (e.g., `seaborn`, `plotly`, `scipy`) via `uv pip install` to make them available to generated code.

### Try It Out with Examples

```bash
# Load example dataset and try visualization
./cli/anyplot test-viz examples/datasets/sales_data.csv \
  --prompt "Create a bar chart showing revenue by region"

# Check privacy budget for sensitive data
./cli/anyplot check-privacy examples/datasets/medical_records.csv \
  --epsilon 0.5

# Run with mock mode (no API key needed)
./scripts/dev-utils.sh mock
```

## 📖 Usage Examples

### Example 1: Sales Analysis

```bash
# Load sales data
cat examples/datasets/sales_data.csv

# In AnyPlot UI, query:
SELECT region, SUM(revenue) as total_revenue 
FROM sales 
GROUP BY region

# Then prompt:
"Create a bar chart showing total revenue by region with different colors for each region"
```

### Example 2: Employee Survey (Privacy-Sensitive)

```bash
# Load survey data (high privacy)
# AnyPlot will use differential privacy

# Query:
SELECT department, AVG(satisfaction_score) as avg_satisfaction
FROM survey
GROUP BY department

# Prompt:
"Show average satisfaction scores by department as a horizontal bar chart"
```

### Example 3: Time Series Data

```bash
# Load IoT sensor data
# Query:
SELECT timestamp, AVG(temperature) as avg_temp
FROM sensors
GROUP BY location

# Prompt:
"Create a line plot showing temperature trends over time for each location"
```

## 🎯 Project Structure

```
anyplot/
├── mcp/                    # Sanctum privacy layer (DP engine, schema masking)
├── server/                 # FastAPI backend (agent orchestration, sandbox)
├── app/                    # React frontend (data upload, SQL editor, viz)
├── cli/                    # Command-line utility
├── examples/               # Example datasets and notebooks
│   └── datasets/          # Sample CSV files
├── scripts/                # Development utilities
├── tests/                  # End-to-end tests
│   └── utils/             # Testing utilities
└── docs/                   # Documentation
    ├── CONTRIBUTING.md    # Contribution guide
    ├── TROUBLESHOOTING.md # Common issues
    └── API.md             # API reference
```

### Authentication

AnyPlot supports two ways to authenticate with Claude:

- **API Key**: Set `ANTHROPIC_API_KEY` as an environment variable or enter it in the Settings panel in the UI. Calls go directly to the Anthropic API.
- **Claude Code subscription**: If you have [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and signed in (e.g., with a Pro or Max plan), AnyPlot detects it automatically — no API key needed. The app uses the Claude Agent SDK to authenticate through your existing Claude Code session.

The Settings panel shows which authentication method is active.

**Note on packages**: Generated visualization code runs in the same Python environment as the backend server. Install additional packages (e.g., `seaborn`, `plotly`, `scipy`) via `uv pip install` to make them available to generated code. The sandbox blocks only dangerous imports (`os`, `subprocess`, `socket`, etc.).

## 🧪 Testing

```bash
# Run all tests (recommended)
./scripts/dev-utils.sh test

# Unit tests only (fast, no API)
uv run pytest mcp/tests/unit server/tests/unit
cd app && npm run test:unit

# Integration tests (with mocking)
uv run pytest server/tests/integration

# E2E tests (requires API key, expensive)
ANTHROPIC_API_KEY=sk-... uv run pytest tests/

# Check code coverage
pytest --cov=server/src --cov=mcp/sanctum_mcp --cov-report=html
```

## 🛠️ CLI Utility

AnyPlot includes a powerful CLI for development and testing:

```bash
# Test visualization without the UI
anyplot test-viz data.csv --prompt "Create a histogram"

# Validate generated code
anyplot validate-code generated_plot.py

# Check privacy budget
anyplot check-privacy sensitive_data.csv --epsilon 0.5

# Export/import sessions
anyplot export-session abc123 --output session.json
anyplot import-session session.json

# Start dev server with example data
anyplot dev-server --load examples/datasets/sales_data.csv

# Generate example visualizations
anyplot generate-examples
```

**Install CLI:**
```bash
# Add to PATH or use directly
export PATH="$PATH:$(pwd)/cli"

# Or install to system
ln -s $(pwd)/cli/anyplot /usr/local/bin/anyplot
```

## ⚙️ Configuration

AnyPlot uses `anyplot.config.json` for configuration:

```json
{
  "privacy": {
    "default_epsilon": 1.0,
    "max_budget_per_session": 10.0
  },
  "sandbox": {
    "timeout_seconds": 30,
    "memory_limit_mb": 512
  },
  "model": {
    "provider": "anthropic",
    "model_name": "claude-sonnet-4"
  }
}
```

**Environment variable overrides:**
```bash
# Override privacy epsilon
export ANYPLOT_PRIVACY_DEFAULT_EPSILON=0.5

# Enable debug mode
export ANYPLOT_DEVELOPMENT_VERBOSE_ERRORS=true
```

See [config.schema.json](./config.schema.json) for all options.

## 📚 Documentation

### For Users
- [README.md](./README.md) - This file
- [Example Datasets](./examples/datasets/README.md) - Sample data and usage
- [Troubleshooting Guide](./docs/TROUBLESHOOTING.md) - Common issues

### For Developers
- [DESIGN.md](./DESIGN.md) - System architecture and security model
- [IMPLEMENTATION.md](./IMPLEMENTATION.md) - Implementation guide
- [CONTRIBUTING.md](./docs/CONTRIBUTING.md) - How to contribute
- [API Reference](./docs/API.md) - API documentation

### For Researchers
- [Privacy Guarantees](./docs/PRIVACY.md) - Differential privacy details
- [Security Model](./DESIGN.md#security-considerations) - Threat model and mitigations

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](./docs/CONTRIBUTING.md) for:

- Development setup
- Code style guidelines
- Testing requirements
- Pull request process

**Quick contribution workflow:**
```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/anyplot.git

# 2. Create branch
git checkout -b feature/your-feature

# 3. Make changes and test
./scripts/dev-utils.sh test

# 4. Submit PR
git push origin feature/your-feature
```

## 🐛 Troubleshooting

**Server won't start?**
```bash
# Check if port is in use
lsof -ti:8000 | xargs kill -9

# Reinstall dependencies
uv pip install -e ./server -e ./mcp
```

**Privacy budget exceeded?**
```json
// Increase in config
{"privacy": {"max_budget_per_session": 20.0}}
```

**More issues?** See [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)

## 📊 Example Datasets

AnyPlot includes 5 example datasets:

1. **Sales Data** - Business analytics (medium privacy)
2. **Survey Results** - Employee data (high privacy)
3. **IoT Sensors** - Time series data (low privacy)
4. **Customer Churn** - Behavioral data (medium privacy)
5. **Medical Records** - Health data (very high privacy)

See [examples/datasets/README.md](./examples/datasets/README.md) for details.

## 🔒 Security & Privacy

### Privacy Guarantees

- **Differential Privacy**: (ε, δ)-DP with configurable epsilon
- **Schema Masking**: Column names hashed before sending to LLM
- **Budget Enforcement**: Strict tracking prevents over-querying
- **No Raw Data Exposure**: Only noisy statistics shared

### Security Features

- **Sandboxed Execution**: Code runs in isolated subprocess
- **Import Restrictions**: Dangerous modules blocked
- **Timeout Protection**: Long-running code terminated
- **Memory Limits**: Prevents resource exhaustion
- **Network Isolation**: No external connections from sandbox

See [DESIGN.md](./DESIGN.md) for threat model and security analysis.
