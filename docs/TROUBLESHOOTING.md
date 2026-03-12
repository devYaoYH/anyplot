# Troubleshooting Guide

Common issues and solutions for AnyPlot.

## 🚀 Installation Issues

### uv not found

**Error:**
```
bash: uv: command not found
```

**Solution:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.cargo/bin:$PATH"
```

### Python version mismatch

**Error:**
```
Python 3.12 or higher required
```

**Solution:**
```bash
# Check Python version
python3 --version

# Install Python 3.12 (Ubuntu/Debian)
sudo apt update
sudo apt install python3.12 python3.12-venv

# Or use pyenv
pyenv install 3.12
pyenv local 3.12
```

### Node.js version mismatch

**Error:**
```
Node.js 20 or higher required
```

**Solution:**
```bash
# Using nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 20
nvm use 20

# Or download from nodejs.org
```

---

## 🖥️ Server Issues

### Port already in use

**Error:**
```
Error: Address already in use (port 8000)
```

**Solution:**
```bash
# Find and kill process using port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
uvicorn server.src.main:app --port 8001
```

### Server won't start

**Error:**
```
ModuleNotFoundError: No module named 'sanctum_mcp'
```

**Solution:**
```bash
# Reinstall dependencies
cd /path/to/anyplot
uv pip install -e ./server -e ./mcp

# Verify installation
uv pip list | grep sanctum
```

### CORS errors

**Error:**
```
Access-Control-Allow-Origin header is missing
```

**Solution:**
```json
// Update anyplot.config.json
{
  "server": {
    "cors_origins": [
      "http://localhost:5173",
      "http://localhost:3000",
      "http://your-frontend-url.com"
    ]
  }
}
```

---

## 🎨 Frontend Issues

### npm install fails

**Error:**
```
npm ERR! peer dependency conflict
```

**Solution:**
```bash
# Clear npm cache
npm cache clean --force

# Delete node_modules and package-lock.json
rm -rf node_modules package-lock.json

# Reinstall
npm install

# If still fails, use --force (not recommended but works)
npm install --force
```

### Frontend can't connect to backend

**Error:**
```
Failed to fetch: http://localhost:8000/visualize
```

**Solution:**
```bash
# 1. Check if backend is running
curl http://localhost:8000/health

# 2. Check backend logs for errors
# Look for CORS or authentication errors

# 3. Verify API URL in frontend config
# app/src/lib/api.ts should point to correct URL

# 4. Restart both servers
```

### Blank page / white screen

**Error:**
White screen with no error in browser

**Solution:**
```bash
# 1. Check browser console for errors (F12)

# 2. Clear browser cache
# Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)

# 3. Rebuild frontend
cd app
rm -rf dist node_modules
npm install
npm run build
npm run dev
```

---

## 🔒 Privacy & Security Issues

### Privacy budget exceeded

**Error:**
```
BudgetExceededError: Privacy budget exhausted (10.0/10.0 epsilon used)
```

**Solution:**
```json
// Option 1: Increase budget in config
{
  "privacy": {
    "max_budget_per_session": 20.0
  }
}

// Option 2: Start a new session
// Click "New Session" in the UI

// Option 3: Use fewer queries
// Be more specific in your prompt to reduce the number of statistical queries
```

### Sandbox timeout

**Error:**
```
SandboxTimeoutError: Code execution exceeded 30 seconds
```

**Solution:**
```json
// Increase timeout in config
{
  "sandbox": {
    "timeout_seconds": 60
  }
}

// Or optimize your visualization prompt
// "Create a simple bar chart" instead of "Create an animated interactive dashboard"
```

### Blocked import error

**Error:**
```
SecurityError: Blocked import: os
```

**Solution:**
```
This is intentional for security!

The sandbox blocks dangerous imports like os, subprocess, socket.

If you need a package:
1. Check if it's in allowed_imports (config)
2. Install it: uv pip install <package>
3. Add to allowed_imports if safe
```

---

## 🧠 Model / API Issues

### API key not found

**Error:**
```
AuthenticationError: ANTHROPIC_API_KEY not set
```

**Solution:**
```bash
# Option 1: Set environment variable
export ANTHROPIC_API_KEY=sk-ant-...

# Option 2: Add to .env file
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Option 3: Enter in Settings UI
# Click Settings → Enter API key → Save

# Verify
echo $ANTHROPIC_API_KEY
```

### Rate limit errors

**Error:**
```
RateLimitError: Rate limit exceeded
```

**Solution:**
```
1. Wait a few minutes and try again
2. Reduce frequency of requests
3. Check your Anthropic plan limits
4. Consider upgrading your API plan
```

### Model timeout

**Error:**
```
TimeoutError: Model request timed out
```

**Solution:**
```json
// Increase model timeout
{
  "model": {
    "timeout_seconds": 120
  }
}

// Or simplify your prompt
// Shorter, more focused prompts = faster responses
```

---

## 📊 Data Issues

### CSV parsing error

**Error:**
```
ParserError: Could not parse CSV
```

**Solution:**
```
1. Check CSV format:
   - UTF-8 encoding
   - Consistent delimiter (comma)
   - Headers in first row
   - No extra blank lines

2. Try opening in Excel/Numbers to verify format

3. Use pandas to clean:
   df = pd.read_csv('data.csv', encoding='utf-8')
   df.to_csv('cleaned.csv', index=False)
```

### SQLite WASM error

**Error:**
```
Error: SQLite WASM initialization failed
```

**Solution:**
```bash
# 1. Check browser compatibility
# Chrome 90+, Firefox 90+, Safari 14+

# 2. Clear browser cache

# 3. Check console for CORS issues
# SQLite WASM files must be served from same origin

# 4. Try a different browser
```

### Data too large

**Error:**
```
Error: Request entity too large
```

**Solution:**
```json
// Increase request size limit
{
  "server": {
    "max_request_size_mb": 100
  }
}

// Or filter data in SQL first
// SELECT * FROM data LIMIT 10000
// Then visualize the filtered result
```

---

## 🧪 Testing Issues

### Tests failing

**Error:**
```
pytest: command not found
```

**Solution:**
```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# If specific test fails, run with verbose output
uv run pytest tests/test_something.py -vv
```

### E2E tests timeout

**Error:**
```
E2E test timeout after 60s
```

**Solution:**
```bash
# E2E tests are slow, increase timeout
pytest tests/test_end_to_end.py --timeout=300

# Or skip E2E tests during development
pytest -m "not e2e"
```

### Mock mode not working

**Error:**
```
Mock mode enabled but still calling real API
```

**Solution:**
```bash
# Ensure environment variable is set
export ANYPLOT_DEVELOPMENT_MOCK_MODE=true
export MOCK_MODE=true

# Restart server after setting
pkill -f uvicorn
uvicorn server.src.main:app --reload
```

---

## 🔧 Configuration Issues

### Config not loading

**Error:**
```
Warning: No configuration file found, using defaults
```

**Solution:**
```bash
# 1. Check config file exists
ls -la anyplot.config.json

# 2. Check config file location
# Must be in project root or set ANYPLOT_CONFIG

# 3. Validate JSON syntax
python -m json.tool anyplot.config.json

# 4. Set explicit path
export ANYPLOT_CONFIG=/path/to/anyplot.config.json
```

### Invalid configuration

**Error:**
```
ConfigError: Invalid configuration schema
```

**Solution:**
```bash
# Validate against schema
# Use online JSON schema validator:
# https://www.jsonschemavalidator.net/

# Or use Python
python -c "
import json
with open('anyplot.config.json') as f:
    config = json.load(f)
    print('Valid JSON!')
"
```

---

## 🐛 Common Debugging Techniques

### Enable debug mode

```bash
# Backend
DEBUG=true uvicorn server.src.main:app --log-level=debug

# Frontend
# Check browser console (F12)

# Both
./scripts/dev-utils.sh start --debug
```

### Check logs

```bash
# Privacy audit log
tail -f logs/privacy_audit.log

# Performance log
tail -f logs/performance.log

# Server logs
# Check terminal where uvicorn is running
```

### Inspect requests

```bash
# Use curl to test API directly
curl -X POST http://localhost:8000/visualize \
  -H "Content-Type: application/json" \
  -d '{"data": [...], "prompt": "plot data"}'

# Or use Postman / Insomnia
```

### Reset everything

```bash
# Nuclear option: reset everything
./scripts/dev-utils.sh clean
rm -rf logs/* generated_code/*
uv pip install -e ./server -e ./mcp
cd app && npm install && cd ..
./scripts/dev-utils.sh start
```

---

## 📚 Still Having Issues?

### Get Help

1. **Check existing issues:** [GitHub Issues](https://github.com/devYaoYH/anyplot/issues)
2. **Search discussions:** [GitHub Discussions](https://github.com/devYaoYH/anyplot/discussions)
3. **Ask for help:** Create a new issue with:
   - Error message (full traceback)
   - Steps to reproduce
   - Your environment (OS, Python version, Node version)
   - Relevant logs

### Provide Context

When asking for help, include:

```bash
# System info
uname -a
python3 --version
node --version
uv --version

# Project info
git branch
git log -1 --oneline

# Config
cat anyplot.config.json

# Logs (last 50 lines)
tail -50 logs/privacy_audit.log
```

---

**Last Updated:** March 12, 2026
