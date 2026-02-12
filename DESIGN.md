# DESIGN.md: AnyPlot System Architecture

**Status:** Approved
**Date:** January 15, 2026
**Maintainers:** Staff Engineering Team
**Version:** 2.0

---

## 1. Executive Summary

**AnyPlot** is a local-first, privacy-preserving analytics platform. It enables users to leverage Large Language Model (LLM) agents (specifically Claude) to visualize sensitive datasets without ever exposing raw row-level data to external model providers.

The core architectural principle is the **"Privacy Firewall"**: a local Model Context Protocol (MCP) layer called **Sanctum** that intercepts agent inquiries, providing only differentially private statistics and masked schemas. The agent returns executable code, which is then run locally against the raw data in a controlled sandbox.

---

## 2. System Architecture

The system adopts a modular, hex-like architecture separated into three top-level domains: **App** (Frontend), **Server** (Orchestration), and **MCP** (Privacy Logic).

### 2.1 High-Level Component Diagram

```mermaid
graph TD
    subgraph "User Workstation (Localhost)"
        subgraph "Frontend (/app)"
            UI[React UI]
            WASM[SQLite WASM]
        end

        subgraph "Backend (/server)"
            API[FastAPI Gateway]
            Orch[Agent Orchestrator]
            Sandbox[Execution Sandbox]
        end

        subgraph "Privacy Layer (/mcp)"
            Proto[MCP Protocol Server]
            DP[Diff. Privacy Engine]
        end
    end

    subgraph "External"
        Claude[Claude API]
    end

    %% Data Flow
    User((User)) -->|1. CSV Upload| UI
    UI -->|2. Local SQL Filter| WASM
    WASM -->|3. Filtered Data| API
    API -->|4. Init Session| Orch

    %% The Privacy Loop
    Orch <-->|5. Stats Request| Proto
    Proto <-->|6. Noise Injection| DP
    Orch <-->|7. Sanitized Context| Claude

    %% Execution
    Claude -->|8. Python Code| Orch
    Orch -->|9. Raw Code| Sandbox
    Sandbox -->|10. Artifact (Image)| API
    API -->|11. Render| UI
```

### 2.2 Data Flow Summary

| Step | From | To | Data |
|------|------|-----|------|
| 1 | User | UI | Raw CSV file |
| 2 | UI | WASM | SQL query |
| 3 | WASM | API | Filtered result set (JSON) |
| 4 | API | Orchestrator | Session init + data |
| 5-6 | Orchestrator | MCP | Stats requests → DP responses |
| 7 | Orchestrator | Claude | Masked schema + noisy stats |
| 8 | Claude | Orchestrator | Generated Python code |
| 9 | Orchestrator | Sandbox | Code string |
| 10 | Sandbox | API | Image bytes |
| 11 | API | UI | Base64 image |

---

## 3. Component Design

### 3.1 Domain: Frontend (`/app`)

**Role:** The user interface for data ingestion, exploration, and visualization requests.

**Tech Stack:**
- React 18+
- TypeScript 5+
- Vite (build tool)
- Tailwind CSS (styling)
- sql.js (SQLite WASM)

**Key Responsibilities:**

| Responsibility | Description |
|----------------|-------------|
| Zero-Server Ingestion | CSVs are parsed and loaded directly into browser memory (SQLite WASM). The server is only contacted when the user explicitly requests a visualization. |
| SQL Exploration | Users refine their dataset using standard SQL queries executed entirely in-browser. |
| Visualization Request | Sends the result of the local SQL query (as JSON) to the backend `/visualize` endpoint. |

**Component Structure:**

```text
/app/src/
├── components/
│   ├── DataUploader.tsx      # CSV drag-and-drop
│   ├── SqlEditor.tsx         # SQL query input
│   ├── DataGrid.tsx          # Query results table
│   ├── VisualizationPanel.tsx # Image display + prompt input
│   └── Layout.tsx            # App shell
├── hooks/
│   ├── useSqlite.ts          # SQLite WASM management
│   └── useVisualize.ts       # API communication
└── lib/
    └── api.ts                # Backend client
```

---

### 3.2 Domain: Server (`/server`)

**Role:** The orchestration layer that manages the lifecycle of the agent and safe code execution.

**Tech Stack:**
- Python 3.12+
- FastAPI
- uv (package management)
- Claude SDK (Anthropic)

**Key Responsibilities:**

| Responsibility | Description |
|----------------|-------------|
| Session Management | Generates unique session IDs for every visualization request. Tracks privacy budget per session. |
| Agent Wrapper | Wraps the Claude SDK, managing context window and system prompts. Registers MCP tools. |
| The Sandbox | A secure execution environment (subprocess) that runs the generated Python code with restricted permissions. |
| Column Mapping | Automatically injects a data-loading preamble that maps masked column names back to real column names. |

**Module Structure:**

```text
/server/src/
├── __init__.py
├── main.py           # FastAPI app + endpoints
├── agent.py          # Claude SDK wrapper
├── sandbox.py        # Subprocess code execution
├── session.py        # Session state management
└── models.py         # Pydantic request/response models
```

**API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /visualize` | POST | Accept data + prompt, return generated image |
| `GET /health` | GET | Healthcheck endpoint |

---

### 3.3 Domain: MCP (`/mcp`)

**Role:** The "Privacy Firewall." This is the only component that has access to raw data statistics while enforcing privacy guarantees.

**Tech Stack:**
- Python 3.12+
- Pydantic (validation)
- NumPy (DP calculations)

**Key Responsibilities:**

| Responsibility | Description |
|----------------|-------------|
| Schema Masking | Converts real column names to hashed identifiers (e.g., `salary` → `col_8f1a`). Type information is preserved. |
| Differential Privacy | Answers statistical queries by calculating the true value, clipping outliers, and adding Laplacian noise. |
| Budget Tracking | Tracks cumulative epsilon spend per session. Rejects queries when budget exhausted. |
| Protocol Implementation | Exposes capabilities via standard MCP tool definitions. |

**Module Structure:**

```text
/mcp/src/
├── __init__.py
├── privacy.py        # DP engine + schema masking
├── server.py         # MCP protocol implementation
├── budget.py         # Privacy budget tracking
└── tools.py          # Tool definitions for Claude
```

**MCP Tools Exposed:**

| Tool | Input | Output |
|------|-------|--------|
| `get_schema` | (none) | `{columns: [{masked_name, dtype}]}` |
| `query_stat` | `{column, statistic}` | `{value, budget_remaining}` |
| `get_histogram` | `{column, bins}` | `{edges, counts, budget_remaining}` |

---

## 4. Data Flow & Security Model

### 4.1 The "Zero-Peek" Policy

**Critical Invariant:** At no point does the Agent Orchestrator or the Claude API receive raw data rows.

**Data Flow Trace:**

```
1. INGEST
   User uploads CSV → Frontend parses → SQLite WASM stores locally

2. QUERY (Local)
   User writes SQL → SQLite WASM executes → Results displayed in browser

3. VISUALIZE REQUEST
   User clicks "Visualize" → Frontend sends result set to /server

4. REGISTRATION
   /server receives data → Registers with /mcp → /mcp stores raw data locally

5. AGENT INQUIRY
   Agent asks: "What is the distribution of col_8f1a?"

6. SANITIZATION
   /mcp calculates histogram → Adds Laplacian noise → Returns noisy bins
   Agent NEVER sees: original column name, raw values, exact statistics

7. CODE GENERATION
   Agent writes: plt.hist(df['col_8f1a'], bins=noisy_bins)

8. RESOLUTION
   /server/src/sandbox.py receives code
   Prepends: df.rename(columns={'salary': 'col_8f1a'})

9. EXECUTION
   Code runs against real data locally → Image produced

10. RESPONSE
    Image bytes returned to frontend → User sees visualization
```

### 4.2 Differential Privacy Implementation

**Mechanism:** Laplace Mechanism for numerical queries.

**Formula:**
```
noisy_value = true_value + Laplace(0, sensitivity / epsilon)
```

**Sensitivity Bounding:**
- Outliers are clipped to `[clip_lower, clip_upper]` before aggregation
- Default bounds: 1st and 99th percentiles of the data
- Sensitivity is then bounded by `clip_upper - clip_lower`

**Budget Management:**

| Operation | Budget Cost |
|-----------|-------------|
| `query_stat` | `epsilon` (configurable, default 1.0) |
| `get_histogram` | `epsilon * num_bins` |
| `get_schema` | 0 (no privacy cost) |

**Session Lifecycle:**
1. Session created with total budget (e.g., `epsilon_total = 10.0`)
2. Each query consumes budget
3. When `budget_remaining <= 0`, all stat queries rejected
4. Session ends when visualization completes or times out

---

## 5. Testing Strategy

We employ a strict **Testing Pyramid** mapped to our directory structure.

### 5.1 Testing Levels

| Level | Scope | Location | Mocking Strategy |
|-------|-------|----------|------------------|
| **Unit** | Pure logic (DP math, SQL parsers, UI components) | `/mcp/tests/unit/`, `/server/tests/unit/`, `/app/tests/unit/` | No mocks. Pure function inputs/outputs. |
| **Integration** | Component communication (API contracts) | `/server/tests/integration/`, `/app/tests/integration/` | Heavy mocking. Server tests mock Claude SDK. App tests mock FastAPI endpoints. |
| **E2E** | "Real world" user flows | `/tests/test_end_to_end.py` | Zero mocking. Uses real `ANTHROPIC_API_KEY`. Spins up real server processes. |

### 5.2 Test Examples

**Unit Test (DP Math):**
```python
# /mcp/tests/unit/test_privacy.py
def test_laplace_noise_distribution():
    """Verify noise follows Laplace distribution with correct scale."""
    epsilon = 1.0
    sensitivity = 100.0
    samples = [add_laplace_noise(0, epsilon, sensitivity) for _ in range(10000)]

    # Scale should be sensitivity / epsilon = 100
    assert abs(np.std(samples) - 100 * np.sqrt(2)) < 10  # Laplace std = scale * sqrt(2)
```

**Integration Test (Mocked Claude):**
```python
# /server/tests/integration/test_api.py
def test_visualize_endpoint_with_mocked_agent(mock_claude):
    """Verify API returns image when agent returns valid code."""
    mock_claude.return_value = "plt.plot([1,2,3])\nplt.savefig('out.png')"

    response = client.post("/visualize", json={"data": [...], "prompt": "plot"})

    assert response.status_code == 200
    assert "image" in response.json()
```

**E2E Test (Real API):**
```python
# /tests/test_end_to_end.py
@pytest.mark.e2e
def test_full_visualization_flow():
    """Full stack test with real Claude API."""
    # Requires ANTHROPIC_API_KEY environment variable
    response = requests.post(
        "http://localhost:8000/visualize",
        json={"data": sample_data, "prompt": "Create a bar chart of values"}
    )

    assert response.status_code == 200
    image_bytes = base64.b64decode(response.json()["image"])
    assert image_bytes[:8] == b'\x89PNG\r\n\x1a\n'  # Valid PNG header
```

### 5.3 CI/CD Pipelines

| Pipeline | Trigger | Tests Run | Duration |
|----------|---------|-----------|----------|
| PR Check | Every PR | Unit + Integration (Mocked) | < 2 minutes |
| Nightly | Daily at 2 AM | Unit + Integration + E2E | ~10 minutes |
| Staging | Pre-deploy | Full E2E suite | ~15 minutes |

---

## 6. Security Considerations

### 6.1 Threat Model

| Threat | Mitigation |
|--------|------------|
| Raw data leakage to Claude | MCP layer only exposes DP-protected statistics. Schema uses hashed column names. |
| Malicious code generation | Sandbox runs in subprocess with no network, restricted filesystem, memory limits. |
| Privacy budget exhaustion attack | Budget tracked per session. Queries rejected when budget depleted. |
| Prompt injection | System prompt clearly scopes agent capabilities. Agent cannot override MCP tools. |

### 6.2 Sandbox Restrictions

The execution sandbox enforces:

- **Network:** No outbound connections
- **Filesystem:** Read/write only to `/tmp/sanctum-<session>/`
- **Timeout:** 30 seconds max execution
- **Memory:** 512MB limit
- **Environment:** Stripped of sensitive variables (`ANTHROPIC_API_KEY`, etc.)
- **Imports:** Allowlist of safe packages (pandas, matplotlib, numpy)

---

## 7. Future Extensibility

### 7.1 Swappable Agents

The `/server` domain uses an `Agent` interface, enabling future support for:

- Local LLMs via Ollama (Llama, Mistral)
- Other cloud providers (OpenAI, Google)
- Custom fine-tuned models

```python
# Example interface
class Agent(Protocol):
    def generate_code(self, prompt: str, tools: list[Tool]) -> str:
        """Generate visualization code given a prompt and available tools."""
        ...
```

### 7.2 Language Support

The Sandbox is currently Python-focused but designed to support additional runtimes:

| Language | Status | Notes |
|----------|--------|-------|
| Python | Supported | matplotlib, seaborn, plotly |
| R | Planned | ggplot2 support |
| JavaScript | Planned | D3.js, Observable Plot |

### 7.3 Data Source Extensions

| Source | Status | Notes |
|--------|--------|-------|
| CSV | Supported | Via frontend upload |
| Parquet | Planned | Efficient columnar format |
| Database connection | Planned | PostgreSQL, MySQL read-only |
| S3/GCS | Planned | Cloud storage integration |

---

## 8. Glossary

| Term | Definition |
|------|------------|
| **MCP** | Model Context Protocol - standard interface for exposing tools to LLM agents |
| **DP** | Differential Privacy - mathematical framework for privacy-preserving data analysis |
| **Epsilon (ε)** | Privacy parameter. Lower values = more noise = stronger privacy guarantees |
| **Sensitivity** | Maximum change in query output from changing one record |
| **Laplace Mechanism** | DP mechanism that adds noise from Laplace distribution scaled by sensitivity/epsilon |
| **Privacy Budget** | Total epsilon that can be spent before no more queries allowed |
| **Masked Schema** | Column names replaced with hashes; types preserved |
