#!/bin/bash
# Development utilities for AnyPlot

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo_info() {
    echo -e "${GREEN}ℹ${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo_error() {
    echo -e "${RED}✗${NC} $1"
}

echo_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function: Setup development environment
setup_dev() {
    echo_info "Setting up development environment..."
    
    cd "$PROJECT_ROOT"
    
    # Install backend dependencies
    echo_info "Installing backend dependencies..."
    uv pip install -e ./server -e ./mcp
    
    # Install frontend dependencies
    echo_info "Installing frontend dependencies..."
    cd app && npm install && cd ..
    
    # Create necessary directories
    mkdir -p logs generated_code examples/datasets
    
    echo_success "Development environment setup complete!"
}

# Function: Run all tests
run_all_tests() {
    echo_info "Running all tests..."
    
    cd "$PROJECT_ROOT"
    
    # Backend unit tests
    echo_info "Running backend unit tests..."
    uv run pytest mcp/tests/unit server/tests/unit
    
    # Frontend tests
    echo_info "Running frontend tests..."
    cd app && npm run test:unit && cd ..
    
    echo_success "All tests passed!"
}

# Function: Start development servers
start_dev_servers() {
    echo_info "Starting development servers..."
    
    cd "$PROJECT_ROOT"
    
    # Start backend in background
    echo_info "Starting backend server (port 8000)..."
    uv run uvicorn server.src.main:app --reload --port 8000 &
    BACKEND_PID=$!
    
    # Wait a bit for backend to start
    sleep 3
    
    # Start frontend
    echo_info "Starting frontend server (port 5173)..."
    cd app && npm run dev &
    FRONTEND_PID=$!
    
    echo_success "Servers started!"
    echo_info "Backend PID: $BACKEND_PID"
    echo_info "Frontend PID: $FRONTEND_PID"
    echo_info "Press Ctrl+C to stop"
    
    # Wait for interrupt
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo_info 'Servers stopped'; exit 0" INT
    wait
}

# Function: Generate example datasets
generate_examples() {
    echo_info "Generating example datasets..."
    
    cd "$PROJECT_ROOT"
    
    python scripts/seed-data.py --type=sales --rows=100 --output=examples/datasets/generated_sales.csv
    python scripts/seed-data.py --type=timeseries --rows=200 --output=examples/datasets/generated_sensors.csv
    python scripts/seed-data.py --type=survey --rows=50 --output=examples/datasets/generated_survey.csv
    
    echo_success "Example datasets generated!"
}

# Function: Clean generated files
clean() {
    echo_info "Cleaning generated files..."
    
    cd "$PROJECT_ROOT"
    
    rm -rf generated_code/*.py
    rm -rf logs/*.log
    rm -rf app/dist
    rm -rf .pytest_cache
    rm -rf **/__pycache__
    
    echo_success "Clean complete!"
}

# Function: Check code style
check_style() {
    echo_info "Checking code style..."
    
    cd "$PROJECT_ROOT"
    
    # Python
    echo_info "Checking Python code..."
    if command -v ruff &> /dev/null; then
        ruff check server/ mcp/
    else
        echo_warn "ruff not found, skipping Python style check"
    fi
    
    # TypeScript
    echo_info "Checking TypeScript code..."
    cd app && npm run lint && cd ..
    
    echo_success "Code style check complete!"
}

# Function: Show project status
show_status() {
    echo_info "AnyPlot Project Status"
    echo "================================"
    
    # Check if servers are running
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo_success "Backend server: Running (port 8000)"
    else
        echo_warn "Backend server: Not running"
    fi
    
    if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo_success "Frontend server: Running (port 5173)"
    else
        echo_warn "Frontend server: Not running"
    fi
    
    # Check configuration
    if [ -f "$PROJECT_ROOT/anyplot.config.json" ]; then
        echo_success "Configuration: Found"
    else
        echo_warn "Configuration: Not found (using defaults)"
    fi
    
    # Check dependencies
    if [ -d "$PROJECT_ROOT/app/node_modules" ]; then
        echo_success "Frontend dependencies: Installed"
    else
        echo_warn "Frontend dependencies: Not installed"
    fi
    
    # Git status
    cd "$PROJECT_ROOT"
    BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
    echo_info "Git branch: $BRANCH"
    
    UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l)
    if [ "$UNCOMMITTED" -gt 0 ]; then
        echo_warn "Uncommitted changes: $UNCOMMITTED files"
    else
        echo_success "Working tree: Clean"
    fi
}

# Function: Run with mock mode
run_mock() {
    echo_info "Starting in mock mode (no API calls)..."
    
    cd "$PROJECT_ROOT"
    
    export MOCK_MODE=true
    export ANYPLOT_DEVELOPMENT_MOCK_MODE=true
    
    "$SCRIPT_DIR/dev-utils.sh" start
}

# Main command dispatcher
case "${1:-help}" in
    setup)
        setup_dev
        ;;
    test)
        run_all_tests
        ;;
    start)
        start_dev_servers
        ;;
    mock)
        run_mock
        ;;
    examples)
        generate_examples
        ;;
    clean)
        clean
        ;;
    style)
        check_style
        ;;
    status)
        show_status
        ;;
    help|*)
        echo "AnyPlot Development Utilities"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  setup     - Setup development environment"
        echo "  test      - Run all tests"
        echo "  start     - Start development servers"
        echo "  mock      - Start with mock API responses"
        echo "  examples  - Generate example datasets"
        echo "  clean     - Clean generated files"
        echo "  style     - Check code style"
        echo "  status    - Show project status"
        echo "  help      - Show this help message"
        ;;
esac
