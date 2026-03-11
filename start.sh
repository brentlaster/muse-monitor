#!/bin/bash
#
# NeuroFocus — Start all components
#
# Usage:
#   ./start.sh          Start server, overlay, and open Chrome
#   ./start.sh --stop   Stop all running NeuroFocus processes
#   ./start.sh --restart  Stop then start
#
# Components:
#   1. neurofocus-server.py   — HTTP server on port 8000
#   2. neurofocus-overlay.py  — macOS window glow overlay
#   3. Chrome browser          — opens the monitor page
#

set -e

PORT=8000
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
URL="http://localhost:${PORT}/muse-focus-monitor.html"
LOG_DIR="${SCRIPT_DIR}/logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No color

header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║          NeuroFocus Launcher v1.0                ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
}

stop_all() {
    echo -e "${YELLOW}Stopping existing NeuroFocus processes...${NC}"
    
    # Close existing NeuroFocus Chrome tabs
    osascript -e '
    tell application "Google Chrome"
        set windowList to every window
        repeat with aWindow in windowList
            set tabList to every tab of aWindow
            repeat with i from (count of tabList) to 1 by -1
                set aTab to item i of tabList
                if URL of aTab contains "muse-focus-monitor" then
                    close aTab
                end if
            end repeat
        end repeat
    end tell
    ' 2>/dev/null && \
        echo -e "  ${GREEN}✓${NC} Closed NeuroFocus Chrome tab(s)" || \
        echo -e "  ${NC}  No Chrome tabs to close"

    # Kill anything on port 8000
    local pids
    pids=$(lsof -ti:${PORT} 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        echo -e "  ${GREEN}✓${NC} Killed server on port ${PORT}"
    else
        echo -e "  ${NC}  No server running on port ${PORT}"
    fi
    
    # Kill overlay processes
    pkill -f "neurofocus-overlay.py" 2>/dev/null && \
        echo -e "  ${GREEN}✓${NC} Killed overlay process" || \
        echo -e "  ${NC}  No overlay running"
    
    # Kill server processes (in case port kill missed it)
    pkill -f "neurofocus-server.py" 2>/dev/null || true
    
    # Brief pause to let ports release
    sleep 1
    echo -e "${GREEN}All NeuroFocus processes stopped.${NC}"
}

check_deps() {
    # Check Python 3
    if ! command -v python3 &>/dev/null; then
        echo -e "${RED}✗ Python 3 not found. Please install Python 3.${NC}"
        exit 1
    fi
    
    # Check for pyobjc (needed for overlay)
    local has_overlay=true
    python3 -c "import AppKit" 2>/dev/null || has_overlay=false
    
    if [ "$has_overlay" = false ]; then
        echo -e "${YELLOW}⚠ PyObjC not installed — overlay will not run${NC}"
        echo -e "  Install with: ${CYAN}pip3 install pyobjc-framework-Cocoa pyobjc-framework-Quartz${NC}"
        echo ""
    fi
    
    echo "$has_overlay"
}

start_all() {
    header
    
    # Check files exist
    if [ ! -f "${SCRIPT_DIR}/neurofocus-server.py" ]; then
        echo -e "${RED}✗ neurofocus-server.py not found in ${SCRIPT_DIR}${NC}"
        exit 1
    fi
    if [ ! -f "${SCRIPT_DIR}/muse-focus-monitor.html" ]; then
        echo -e "${RED}✗ muse-focus-monitor.html not found in ${SCRIPT_DIR}${NC}"
        exit 1
    fi
    
    # Stop any existing instances
    stop_all
    echo ""
    
    # Check dependencies
    local has_overlay
    has_overlay=$(check_deps)
    
    # Create logs directory
    mkdir -p "${LOG_DIR}"
    
    # Start server
    echo -e "${CYAN}Starting server on port ${PORT}...${NC}"
    cd "${SCRIPT_DIR}"
    python3 neurofocus-server.py > "${LOG_DIR}/server.log" 2>&1 &
    local server_pid=$!
    sleep 1
    
    # Verify server started
    if kill -0 $server_pid 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Server running (PID ${server_pid})"
    else
        echo -e "  ${RED}✗ Server failed to start. Check ${LOG_DIR}/server.log${NC}"
        exit 1
    fi
    
    # Start overlay (if pyobjc available)
    if [ "$has_overlay" = "true" ] && [ -f "${SCRIPT_DIR}/neurofocus-overlay.py" ]; then
        echo -e "${CYAN}Starting overlay...${NC}"
        python3 neurofocus-overlay.py > "${LOG_DIR}/overlay.log" 2>&1 &
        local overlay_pid=$!
        sleep 1
        if kill -0 $overlay_pid 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} Overlay running (PID ${overlay_pid})"
        else
            echo -e "  ${YELLOW}⚠ Overlay failed to start. Check ${LOG_DIR}/overlay.log${NC}"
        fi
    fi
    
    # Open Chrome
    echo -e "${CYAN}Opening Chrome...${NC}"
    if command -v open &>/dev/null; then
        open -a "Google Chrome" "${URL}" 2>/dev/null || open "${URL}" 2>/dev/null || true
        echo -e "  ${GREEN}✓${NC} Opened ${URL}"
    else
        echo -e "  ${YELLOW}⚠ Could not open browser. Navigate to: ${URL}${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  NeuroFocus is running!                          ║${NC}"
    echo -e "${GREEN}║                                                  ║${NC}"
    echo -e "${GREEN}║  App:     ${URL}${NC}"
    echo -e "${GREEN}║  Logs:    ${LOG_DIR}/${NC}"
    echo -e "${GREEN}║                                                  ║${NC}"
    echo -e "${GREEN}║  To stop: ./start.sh --stop                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Wait for Ctrl+C
    echo -e "Press ${YELLOW}Ctrl+C${NC} to stop all components..."
    trap 'echo ""; stop_all; exit 0' INT TERM
    
    # Tail logs so user sees output
    tail -f "${LOG_DIR}/server.log" "${LOG_DIR}/overlay.log" 2>/dev/null || wait
}

# Parse arguments
case "${1:-}" in
    --stop|-s)
        header
        stop_all
        ;;
    --restart|-r)
        start_all
        ;;
    --help|-h)
        header
        echo "Usage:"
        echo "  ./start.sh            Start all components"
        echo "  ./start.sh --stop     Stop all running processes"
        echo "  ./start.sh --restart  Stop then start"
        echo "  ./start.sh --help     Show this help"
        ;;
    *)
        start_all
        ;;
esac
