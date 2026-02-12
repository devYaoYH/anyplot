# IMPLEMENTATION.md: AnyPlot

**Status:** Draft v1.0
**Date:** January 15, 2026
**Owner:** Staff Engineering Team
**Context:** Local-first, privacy-preserving data visualization agent.

---

## 1. Project Overview

AnyPlot is a standalone application allowing researchers to visualize sensitive datasets using the Claude Code SDK without exposing row-level data. It uses a **Local MCP (Model Context Protocol)** layer called **Sanctum** to intercept agent requests and apply Differential Privacy (DP) before data leaves the secure context.

### Key Objectives

1. **Privacy:** No raw data ever leaves the local machine or is exposed to the LLM context window.
2. **Local Execution:** All code generation and execution happen locally.
3. **Modern Stack:** Python 3.12+ (Backend), React/TypeScript (Frontend), SQLite WASM.

---

## 2. Directory Structure & Tech Stack

We use **uv** for Python package management and **Vite** for the frontend.

```text
anyplot/
├── mcp/                            # [CORE] Sanctum Privacy & Data Layer (Python)
│   ├── src/
│   │   ├── __init__.py
│   │   ├── privacy.py              # DP logic & masking
│   │   └── server.py               # MCP protocol implementation
│   ├── tests/
│   │   └── unit/                   # Unit tests for DP math
│   └── pyproject.toml
│
├── server/                         # [ORCHESTRATION] FastAPI & Agent (Python)
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                 # API entrypoint
│   │   ├── agent.py                # Claude Code SDK wrapper
│   │   └── sandbox.py              # Code execution environment
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/            # API tests with mocked Claude
│   └── pyproject.toml
│
├── app/                            # [UI] Frontend (React + TypeScript)
│   ├── src/
│   │   └── components/             # Visualizer, SQL Editor
│   ├── tests/
│   │   ├── unit/                   # Vitest component tests
│   │   └── integration/            # Playwright tests (mocked backend)
│   ├── package.json
│   └── vite.config.ts
│
└── tests/                          # [E2E] Full-stack smoke tests
    └── test_end_to_end.py          # Real Anthropic API calls
```

---

## 3. Development Phases

### Phase 1: The Privacy Core (`/mcp`)

**Objective:** Build the "Firewall" that masks data and enforces differential privacy.

#### 3.1.1 Schema Extraction (`privacy.py`)

Create logic to read a Pandas DataFrame and return a masked schema:

- **Input:** Raw DataFrame with columns like `salary`, `age`, `ssn`
- **Output:** Schema with hashed column names (e.g., `salary` → `col_a1b2`) but preserved types
- **Requirement:** Original column names must NEVER appear in the output

```python
# Example interface
def extract_masked_schema(df: pd.DataFrame) -> dict[str, MaskedColumn]:
    """
    Returns mapping of masked_name -> MaskedColumn(original_name, dtype).
    The original_name is stored locally but never sent to the agent.
    """
    pass
```

#### 3.1.2 Differential Privacy (`privacy.py`)

Implement `query_aggregate()` for noisy statistical queries:

- **Input:** `col_hash`, `statistic` (mean/max/min/count/sum), `epsilon` (privacy budget)
- **Logic:** Calculate true value → Clip outliers → Add Laplacian noise → Return noisy value
- **Sensitivity:** Must bound sensitivity via clipping before adding noise

```python
# Example interface
def query_aggregate(
    df: pd.DataFrame,
    col_hash: str,
    statistic: Literal["mean", "max", "min", "count", "sum"],
    epsilon: float = 1.0,
    clip_bounds: tuple[float, float] | None = None,
) -> float:
    """Returns a differentially private aggregate statistic."""
    pass
```

#### 3.1.3 MCP Server (`server.py`)

Implement the Model Context Protocol to expose these tools to the Agent:

- `get_schema`: Returns masked schema (column hashes + types)
- `query_stat`: Returns DP-protected aggregate statistic
- `get_histogram`: Returns DP-protected histogram bins

#### 3.1.4 Definition of Done

- [ ] Unit tests verify noise follows Laplace distribution with correct scale
- [ ] Schema extraction never leaks original column names (test with PII column names)
- [ ] Privacy budget tracking prevents over-querying
- [ ] MCP server responds to tool calls correctly

---

### Phase 2: The Server & Sandbox (`/server`)

**Objective:** Orchestrate the Agent and execute generated code safely.

#### 3.2.1 FastAPI Setup (`main.py`)

Create the following endpoints:

| Endpoint | Method | Request Body | Response |
|----------|--------|--------------|----------|
| `/visualize` | POST | `{data: JSON/Arrow, prompt: string}` | `{image: base64, code: string}` |
| `/health` | GET | — | `{status: "ok"}` |

#### 3.2.2 Sandbox (`sandbox.py`)

The sandbox executes agent-generated Python code:

1. **Input:** String of Python code from the agent
2. **Prelude Injection:** Automatically prepend code that:
   - Loads the real DataFrame
   - Renames columns from masked names → real names
   - Sets up matplotlib with `Agg` backend
3. **Execution:** Run in subprocess with restricted environment
4. **Output Capture:** Capture `stdout`, `stderr`, and image bytes from `plt.savefig()`

```python
# Example prelude (auto-injected, not visible to agent)
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

df = __sanctum_load_data__()
df = df.rename(columns={'col_a1b2': 'salary', 'col_c3d4': 'age'})
```

**Security requirements:**
- No network access from subprocess
- No file system access outside temp directory
- Timeout after 30 seconds
- Memory limit enforced

#### 3.2.3 Agent Orchestration (`agent.py`)

Initialize and manage the Claude Code SDK:

1. **Initialize:** Create Claude client with MCP tools registered
2. **System Prompt:**
   ```
   You are a data visualization assistant. You cannot see raw data rows—only
   aggregate statistics via the provided tools. Generate Python/matplotlib
   code to visualize the data based on the user's request and the statistics
   you retrieve.
   ```
3. **Tool Registration:** Register `/mcp` tools (get_schema, query_stat, get_histogram)
4. **Response Handling:** Extract generated Python code from agent response

#### 3.2.4 Definition of Done

- [ ] `test_sandbox_execution`: Given hardcoded plot code, produces valid PNG
- [ ] `test_sandbox_security`: Subprocess cannot access network or filesystem
- [ ] `test_api_integration`: Full request/response cycle with mocked Claude (returns canned code)
- [ ] `test_column_mapping`: Masked columns correctly mapped back to real names

---

### Phase 3: The Frontend (`/app`)

**Objective:** A modern interface for data loading and query formulation.

#### 3.3.1 Data Ingestion

- Use `react-dropzone` to accept CSV file uploads
- Parse CSV client-side using `papaparse`
- Load parsed data into `sql.js` (SQLite WASM) for local querying

#### 3.3.2 Local SQL Interface

- Provide a SQL editor component (consider `react-codemirror` with SQL mode)
- Execute queries against the local SQLite database
- Display results in a data grid component
- **Important:** All SQL execution happens in-browser; no server round-trip

#### 3.3.3 Visualization Request Flow

1. User writes SQL query and clicks "Run" → Results displayed locally
2. User clicks "Visualize" → Frontend extracts current result set
3. Result set + user prompt sent to `POST /visualize`
4. Backend returns base64 image → Frontend renders in `<img>` tag

#### 3.3.4 Definition of Done

- [ ] User can upload CSV and see it in a table
- [ ] User can run SQL queries and see filtered results
- [ ] Vitest component tests pass for all UI components
- [ ] Playwright integration tests pass (mocked `/visualize` endpoint)

---

## 4. Testing Strategy

We enforce a strict **Testing Pyramid**.

### Level 1: Unit Tests

| Location | Scope | Command |
|----------|-------|---------|
| `/mcp/tests/unit/` | DP math, schema masking | `uv run pytest mcp/tests/unit/` |
| `/server/tests/unit/` | Sandbox logic, API parsing | `uv run pytest server/tests/unit/` |
| `/app/tests/unit/` | React components | `npm run test:unit` |

**Rules:**
- NO network calls
- NO mocks (test pure functions)
- Fast execution (<10 seconds total)

### Level 2: Integration Tests (Mocked)

| Location | Scope | Mocking Strategy |
|----------|-------|------------------|
| `/server/tests/integration/` | FastAPI ↔ MCP communication | Mock Claude SDK responses |
| `/app/tests/integration/` | UI ↔ Backend contracts | Mock `/visualize` endpoint |

**Rules:**
- Mock external dependencies (Claude API, backend endpoints)
- Test component interactions
- Verify API contracts

### Level 3: End-to-End Tests (Real)

| Location | Scope | Command |
|----------|-------|---------|
| `/tests/test_end_to_end.py` | Full stack with real Claude | `ANTHROPIC_API_KEY=sk-... uv run pytest tests/` |

**What it tests:**
1. Spins up real FastAPI server
2. Spins up real MCP server
3. Sends real request to Claude API
4. Verifies a valid image is produced

**Rules:**
- Run only on pre-merge or nightly builds (expensive)
- Requires valid `ANTHROPIC_API_KEY`
- Timeout: 5 minutes per test

---

## 5. Quick Start (Developer Guide)

### Prerequisites

- Python 3.12+
- Node.js 20+
- uv (Python package manager)

### Installation

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and enter project
git clone <repo-url> sanctum
cd sanctum

# 3. Setup Backend (Server + MCP)
uv venv
uv pip install -e ./server -e ./mcp

# 4. Setup Frontend
cd app
npm install
cd ..
```

### Running Locally

```bash
# Terminal 1: Start backend server
uv run uvicorn server.src.main:app --reload --port 8000

# Terminal 2: Start frontend dev server
cd app && npm run dev
```

### Running Tests

```bash
# Unit tests only (fast, no API calls)
uv run pytest mcp/tests/unit server/tests/unit
cd app && npm run test:unit

# Integration tests (mocked)
uv run pytest server/tests/integration
cd app && npm run test:integration

# E2E tests (requires API key, expensive)
ANTHROPIC_API_KEY=sk-... uv run pytest tests/
```

---

## 6. Security & Privacy Constraints

### 6.1 Zero-Peeking Policy

The Agent (Claude) must **NEVER** receive raw data rows. It can only access:
- Masked schema (hashed column names + types)
- DP-protected aggregate statistics
- DP-protected histograms

### 6.2 Differential Privacy Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `epsilon` | 1.0 | Privacy budget per query (lower = more private) |
| `clip_lower` | Auto (1st percentile) | Lower bound for outlier clipping |
| `clip_upper` | Auto (99th percentile) | Upper bound for outlier clipping |

**Budget tracking:** Each session starts with a total budget. Queries consume budget. When exhausted, no more queries allowed.

### 6.3 Sandbox Security

Generated code executes in a subprocess with:
- No network access (`--network=none` if using container)
- No filesystem access outside `/tmp/sanctum-<session-id>/`
- 30-second timeout
- 512MB memory limit
- Restricted environment variables (no `ANTHROPIC_API_KEY`, etc.)

---

## 7. Appendix: Key Interfaces

### MCP Tool Definitions

```python
# get_schema tool
{
    "name": "get_schema",
    "description": "Get the masked schema of the dataset",
    "input_schema": {},
    "output_schema": {
        "columns": [{"masked_name": "str", "dtype": "str"}]
    }
}

# query_stat tool
{
    "name": "query_stat",
    "description": "Get a DP-protected aggregate statistic",
    "input_schema": {
        "column": "str",      # masked column name
        "statistic": "str",   # mean|max|min|count|sum
    },
    "output_schema": {
        "value": "float",
        "budget_remaining": "float"
    }
}
```

### API Request/Response Examples

```bash
# POST /visualize
curl -X POST http://localhost:8000/visualize \
  -H "Content-Type: application/json" \
  -d '{
    "data": [{"col_a1b2": 50000, "col_c3d4": 30}, ...],
    "prompt": "Create a histogram of salaries"
  }'

# Response
{
  "image": "iVBORw0KGgoAAAANS...",  # base64 PNG
  "code": "import matplotlib.pyplot as plt\n..."
}
```
