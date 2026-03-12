# Contributing to AnyPlot

Thank you for your interest in contributing to AnyPlot! This guide will help you get started.

## 🎯 Quick Start

### Prerequisites

- **Python:** 3.12 or higher
- **Node.js:** 20 or higher
- **uv:** Python package manager ([install](https://github.com/astral-sh/uv))
- **Git:** For version control

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/devYaoYH/anyplot.git
cd anyplot

# Checkout the improvements branch (or create your own)
git checkout -b your-feature-branch

# Run setup script
./scripts/dev-utils.sh setup

# Or manually:
# Backend
uv venv && uv pip install -e ./server -e ./mcp

# Frontend
cd app && npm install && cd ..
```

### Running the Project

```bash
# Start both servers (recommended for development)
./scripts/dev-utils.sh start

# Or start separately:
# Terminal 1: Backend
uv run uvicorn server.src.main:app --reload --port 8000

# Terminal 2: Frontend
cd app && npm run dev
```

### Running Tests

```bash
# All tests
./scripts/dev-utils.sh test

# Unit tests only (fast)
uv run pytest mcp/tests/unit server/tests/unit
cd app && npm run test:unit

# E2E tests (requires API key)
ANTHROPIC_API_KEY=sk-... uv run pytest tests/
```

---

## 📁 Project Structure

```
anyplot/
├── mcp/                    # Privacy layer (Sanctum MCP)
│   ├── sanctum_mcp/       # Main package
│   │   ├── privacy.py     # Differential privacy logic
│   │   ├── server.py      # MCP protocol implementation
│   │   ├── budget.py      # Privacy budget tracking
│   │   └── tools.py       # MCP tool definitions
│   └── tests/
│       └── unit/          # Unit tests for privacy logic
│
├── server/                 # Backend (FastAPI)
│   ├── src/
│   │   ├── main.py        # API endpoints
│   │   ├── agent.py       # Claude SDK wrapper
│   │   ├── sandbox.py     # Code execution sandbox
│   │   ├── config.py      # Configuration management
│   │   └── models.py      # Pydantic models
│   └── tests/
│       ├── unit/          # Unit tests
│       └── integration/   # Integration tests
│
├── app/                    # Frontend (React + TypeScript)
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom React hooks
│   │   ├── lib/           # Utilities
│   │   └── types/         # TypeScript types
│   └── tests/             # Frontend tests
│
├── cli/                    # CLI utility
│   └── anyplot            # Main CLI script
│
├── examples/               # Example datasets and notebooks
│   └── datasets/          # Sample CSV files
│
├── scripts/                # Development utilities
│   ├── seed-data.py       # Generate test data
│   └── dev-utils.sh       # Dev helper commands
│
└── tests/                  # End-to-end tests
    └── test_end_to_end.py
```

---

## 🔧 Development Workflow

### 1. Pick an Issue

- Check the [issue tracker](https://github.com/devYaoYH/anyplot/issues)
- Look for issues labeled `good first issue` or `help wanted`
- Comment on the issue to let others know you're working on it

### 2. Create a Branch

```bash
# Feature branch
git checkout -b feature/your-feature-name

# Bug fix branch
git checkout -b fix/bug-description
```

### 3. Make Changes

- Write code following the project's style guidelines
- Add tests for new functionality
- Update documentation if needed

### 4. Test Your Changes

```bash
# Run tests
./scripts/dev-utils.sh test

# Check code style
./scripts/dev-utils.sh style

# Test manually
./scripts/dev-utils.sh start
```

### 5. Commit Changes

```bash
# Use conventional commits format
git commit -m "feat: add new privacy metric"
git commit -m "fix: resolve sandbox timeout issue"
git commit -m "docs: update API reference"
```

**Commit message format:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions or changes
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `chore:` Build/tooling changes

### 6. Submit Pull Request

```bash
# Push your branch
git push origin your-branch-name

# Create PR on GitHub
# Include:
# - Description of changes
# - Related issue number (#123)
# - Screenshots (for UI changes)
# - Test results
```

---

## 🎨 Code Style Guidelines

### Python

**Style:** PEP 8 compliant

```python
# Good: descriptive names, type hints
def calculate_noisy_mean(
    values: list[float], 
    epsilon: float, 
    clip_bounds: tuple[float, float]
) -> float:
    """Calculate differentially private mean with clipping."""
    clipped = [max(clip_bounds[0], min(v, clip_bounds[1])) for v in values]
    true_mean = sum(clipped) / len(clipped)
    noise = sample_laplace_noise(epsilon, clip_bounds[1] - clip_bounds[0])
    return true_mean + noise

# Bad: unclear names, no types
def calc(v, e, c):
    cl = [max(c[0], min(x, c[1])) for x in v]
    m = sum(cl) / len(cl)
    return m + noise(e, c[1] - c[0])
```

**Key principles:**
- Use type hints everywhere
- Docstrings for all public functions
- Descriptive variable names
- Keep functions focused and small
- Prefer explicit over implicit

### TypeScript

**Style:** Consistent with project conventions

```typescript
// Good: typed, clear intent
interface VisualizationRequest {
  data: Record<string, unknown>[];
  prompt: string;
  sessionId?: string;
}

async function generateVisualization(
  request: VisualizationRequest
): Promise<VisualizationResponse> {
  const response = await api.post('/visualize', request);
  return response.data;
}

// Bad: untyped, unclear
async function genViz(req: any) {
  const res = await api.post('/visualize', req);
  return res.data;
}
```

**Key principles:**
- Use TypeScript strictly (no `any` unless absolutely necessary)
- Interfaces for data structures
- Functional components with hooks
- Proper error handling
- Meaningful component names

---

## 🧪 Testing Guidelines

### Test Structure

We follow the **testing pyramid**:

```
         /\
        /  \  E2E Tests (Few, expensive)
       /    \
      /------\  Integration Tests (Some, moderate)
     /--------\
    /----------\  Unit Tests (Many, fast)
   /____________\
```

### Writing Tests

**Unit tests:**
```python
# Test pure functions with no dependencies
def test_laplace_noise_distribution():
    """Verify noise follows Laplace distribution."""
    samples = [add_laplace_noise(0, epsilon=1.0, sensitivity=1.0) 
               for _ in range(10000)]
    
    # Laplace std = scale * sqrt(2), scale = sensitivity / epsilon
    expected_std = 1.0 * np.sqrt(2)
    assert abs(np.std(samples) - expected_std) < 0.1
```

**Integration tests:**
```python
# Test component interactions with mocking
def test_visualize_endpoint(mock_claude):
    """Test API endpoint with mocked Claude."""
    mock_claude.return_value = "plt.plot([1,2,3])"
    
    response = client.post("/visualize", json={
        "data": [{"x": 1, "y": 2}],
        "prompt": "plot data"
    })
    
    assert response.status_code == 200
    assert "image" in response.json()
```

**E2E tests:**
```python
# Test full flow with real API (expensive, run sparingly)
@pytest.mark.e2e
def test_full_visualization_flow():
    """End-to-end test with real Claude API."""
    # Requires ANTHROPIC_API_KEY
    response = requests.post("http://localhost:8000/visualize", ...)
    assert response.status_code == 200
```

### Test Coverage

- **Required:** All new code should have unit tests
- **Goal:** 80%+ coverage for critical paths
- **Privacy code:** 100% coverage (security-critical)

```bash
# Check coverage
pytest --cov=server/src --cov=mcp/sanctum_mcp --cov-report=html
```

---

## 🔒 Security & Privacy

### Privacy-Critical Code

Any code that handles data privacy requires extra scrutiny:

```python
# CRITICAL: Privacy budget enforcement
def query_statistic(self, column: str, stat: str, epsilon: float):
    # Must check budget BEFORE computing
    if not self.budget.can_spend(epsilon):
        raise BudgetExceededError("Privacy budget exhausted")
    
    # Compute with DP protection
    result = self._compute_noisy_statistic(column, stat, epsilon)
    
    # Must spend budget AFTER successful computation
    self.budget.spend(epsilon)
    
    return result
```

**Review checklist for privacy code:**
- [ ] Budget checked before computation
- [ ] Noise added correctly (Laplace mechanism)
- [ ] Sensitivity properly bounded
- [ ] No raw data leakage
- [ ] All edge cases handled

### Sandbox Security

Code execution must be sandboxed:

```python
# CRITICAL: Validate imports before execution
BLOCKED_IMPORTS = ["os", "subprocess", "socket", "sys"]

def validate_code(code: str) -> bool:
    for blocked in BLOCKED_IMPORTS:
        if f"import {blocked}" in code:
            raise SecurityError(f"Blocked import: {blocked}")
    return True
```

---

## 📝 Documentation

### Code Documentation

**Python docstrings:**
```python
def add_laplace_noise(value: float, epsilon: float, sensitivity: float) -> float:
    """
    Add Laplace noise for differential privacy.
    
    Args:
        value: The true value to protect
        epsilon: Privacy parameter (lower = more privacy)
        sensitivity: Maximum change from one record
    
    Returns:
        The value with Laplace noise added
    
    Example:
        >>> add_laplace_noise(100.0, epsilon=1.0, sensitivity=10.0)
        98.234  # Value with noise
    """
    scale = sensitivity / epsilon
    noise = np.random.laplace(0, scale)
    return value + noise
```

**TypeScript JSDoc:**
```typescript
/**
 * Generate a visualization from data and prompt
 * 
 * @param data - Array of data records
 * @param prompt - Natural language prompt
 * @param sessionId - Optional session ID for privacy budget tracking
 * @returns Visualization response with image and code
 * 
 * @example
 * const result = await generateVisualization(
 *   [{x: 1, y: 2}],
 *   "Create a scatter plot"
 * );
 */
async function generateVisualization(...) { ... }
```

### User Documentation

When adding features, update:
- README.md (if user-facing)
- API.md (for API changes)
- Example datasets (for new data types)

---

## 🐛 Debugging Tips

### Backend Debugging

```bash
# Enable debug logging
DEBUG=true uv run uvicorn server.src.main:app --reload

# Use Python debugger
# Add: import pdb; pdb.set_trace()

# Check logs
tail -f logs/privacy_audit.log
```

### Frontend Debugging

```bash
# React DevTools in browser
# Use browser console for debugging

# Check API calls
# Network tab in DevTools

# Component debugging
console.log('Debug:', {data, state, props});
```

### Common Issues

**Issue: "Module not found"**
```bash
# Reinstall dependencies
uv pip install -e ./server -e ./mcp
cd app && npm install
```

**Issue: "Port already in use"**
```bash
# Kill processes on port
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```

**Issue: "Privacy budget exceeded"**
```python
# Clear session or increase budget in config
config.privacy.max_budget_per_session = 20.0
```

---

## 📚 Additional Resources

- [Architecture Overview](../DESIGN.md)
- [Implementation Guide](../IMPLEMENTATION.md)
- [API Reference](./API.md)
- [Testing Guide](./TESTING.md)

---

## 💬 Getting Help

- **Questions:** Open a [GitHub Discussion](https://github.com/devYaoYH/anyplot/discussions)
- **Bugs:** File an [Issue](https://github.com/devYaoYH/anyplot/issues)
- **Chat:** Join our [Discord](https://discord.gg/anyplot) (if available)

---

## 🎉 Recognition

Contributors are recognized in:
- README.md contributors section
- Release notes for significant features
- Annual contributor spotlight

Thank you for making AnyPlot better! 🚀
