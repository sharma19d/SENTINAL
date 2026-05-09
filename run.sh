#!/usr/bin/env bash
# SENTINEL — Full System Startup Script
# Run from the project root: bash run.sh

set -e
cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}╔════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       SENTINEL — Startup           ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════╝${NC}"

# ── 1. Redis ─────────────────────────────────────────────────────
echo -e "\n${YELLOW}[1/7] Checking Redis...${NC}"
if redis-cli ping &>/dev/null; then
  echo -e "  ${GREEN}✓ Redis is running${NC}"
else
  echo -e "  Starting Redis..."
  redis-server --daemonize yes
  sleep 1
  redis-cli ping &>/dev/null && echo -e "  ${GREEN}✓ Redis started${NC}" || { echo -e "  ${RED}✗ Redis failed to start${NC}"; exit 1; }
fi

# ── 2. Backend API ───────────────────────────────────────────────
echo -e "\n${YELLOW}[2/7] Starting Backend API (port 8000)...${NC}"

pkill -f "uvicorn api.main" 2>/dev/null || true
sleep 1

# Use venv if available, fall back to system python
if [ -f "env/bin/uvicorn" ]; then
  UVICORN="env/bin/uvicorn"
  PYTHON="$PROJECT_ROOT/env/bin/python"
else
  UVICORN="uvicorn"
  PYTHON="$(which python3)"
fi

PYTHONPATH="$PROJECT_ROOT" $UVICORN api.main:app \
  --host 0.0.0.0 --port 8000 \
  --log-level warning \
  > logs/api.log 2>&1 &
API_PID=$!

echo -n "  Waiting for API"
for i in {1..15}; do
  sleep 1
  if curl -sf http://localhost:8000/api/health &>/dev/null; then
    echo -e "\n  ${GREEN}✓ API running (PID $API_PID) → http://localhost:8000${NC}"
    break
  fi
  echo -n "."
  if [ $i -eq 15 ]; then
    echo -e "\n  ${RED}✗ API failed to start. Check logs/api.log:${NC}"
    tail -20 logs/api.log
    exit 1
  fi
done

# ── 3. Packet Capture (Layer 1, requires sudo) ───────────────────
echo -e "\n${YELLOW}[3/7] Starting Packet Capture on wlan0...${NC}"

pkill -f "sentinel.core.capture.main" 2>/dev/null || true
echo "charon" | sudo -S pkill -f "sentinel.core.capture.main" 2>/dev/null || true
sleep 1

# sudo env explicitly passes PYTHONPATH through to the root process
echo "charon" | sudo -S env PYTHONPATH="$PROJECT_ROOT" "$PYTHON" -m sentinel.core.capture.main \
  --interface wlan0 \
  --publish-packets \
  > logs/capture.log 2>&1 &
CAPTURE_PID=$!

sleep 2
if kill -0 $CAPTURE_PID 2>/dev/null; then
  echo -e "  ${GREEN}✓ Capture running (PID $CAPTURE_PID) → wlan0${NC}"
else
  echo -e "  ${RED}✗ Capture failed to start. Check logs/capture.log:${NC}"
  tail -10 logs/capture.log
  echo -e "  ${YELLOW}  Continuing without live capture...${NC}"
fi

# ── 4. Anomaly Detection Worker (Agent 1) ────────────────────────
echo -e "\n${YELLOW}[4/7] Starting Anomaly Detection Worker...${NC}"

pkill -f "sentinel.agents.anomaly.worker" 2>/dev/null || true
sleep 1

PYTHONPATH="$PROJECT_ROOT" $PYTHON -m sentinel.agents.anomaly.worker \
  > logs/anomaly.log 2>&1 &
ANOMALY_PID=$!

sleep 1
if kill -0 $ANOMALY_PID 2>/dev/null; then
  echo -e "  ${GREEN}✓ Anomaly worker running (PID $ANOMALY_PID)${NC}"
else
  echo -e "  ${RED}✗ Anomaly worker failed. Check logs/anomaly.log${NC}"
  tail -5 logs/anomaly.log
fi

# ── 5. Classifier Worker (Agent 2 — Gemma LLM) ──────────────────
echo -e "\n${YELLOW}[5/7] Starting Classifier Worker (Gemma)...${NC}"

pkill -f "sentinel.agents.classifier.worker" 2>/dev/null || true
sleep 1

PYTHONPATH="$PROJECT_ROOT" $PYTHON -m sentinel.agents.classifier.worker \
  > logs/classifier.log 2>&1 &
CLASSIFIER_PID=$!

sleep 1
if kill -0 $CLASSIFIER_PID 2>/dev/null; then
  echo -e "  ${GREEN}✓ Classifier worker running (PID $CLASSIFIER_PID)${NC}"
else
  echo -e "  ${RED}✗ Classifier worker failed. Check logs/classifier.log${NC}"
  tail -5 logs/classifier.log
fi

# ── 6. Responder Worker (Agent 3 — LangGraph) ───────────────────
echo -e "\n${YELLOW}[6/7] Starting Responder Worker (LangGraph)...${NC}"

pkill -f "sentinel.agents.responder.worker" 2>/dev/null || true
sleep 1

PYTHONPATH="$PROJECT_ROOT" $PYTHON -m sentinel.agents.responder.worker \
  > logs/responder.log 2>&1 &
RESPONDER_PID=$!

sleep 1
if kill -0 $RESPONDER_PID 2>/dev/null; then
  echo -e "  ${GREEN}✓ Responder worker running (PID $RESPONDER_PID)${NC}"
else
  echo -e "  ${RED}✗ Responder worker failed. Check logs/responder.log${NC}"
  tail -5 logs/responder.log
fi

# ── 7. Frontend Dashboard ────────────────────────────────────────
echo -e "\n${YELLOW}[7/7] Starting Frontend Dashboard (port 3000)...${NC}"

pkill -f "vite.*dashboard" 2>/dev/null || true
sleep 1

cd dashboard
npm run dev > ../logs/dashboard.log 2>&1 &
DASH_PID=$!
cd ..

sleep 3
echo -e "  ${GREEN}✓ Dashboard running (PID $DASH_PID) → http://localhost:3000${NC}"

# ── Done ─────────────────────────────────────────────────────────
echo -e "\n${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          SENTINEL is running!                  ║${NC}"
echo -e "${GREEN}║                                                ║${NC}"
echo -e "${GREEN}║  Dashboard  → http://localhost:3000            ║${NC}"
echo -e "${GREEN}║  API        → http://localhost:8000            ║${NC}"
echo -e "${GREEN}║  API Docs   → http://localhost:8000/docs       ║${NC}"
echo -e "${GREEN}║                                                ║${NC}"
echo -e "${GREEN}║  Live capture on wlan0 → all 3 AI agents       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Logs:"
echo -e "    ${CYAN}logs/api.log${NC}        Backend API"
echo -e "    ${CYAN}logs/capture.log${NC}    Layer 1 packet capture"
echo -e "    ${CYAN}logs/anomaly.log${NC}    Agent 1 — LSTM anomaly detection"
echo -e "    ${CYAN}logs/classifier.log${NC} Agent 2 — Gemma threat classifier"
echo -e "    ${CYAN}logs/responder.log${NC}  Agent 3 — LangGraph responder"
echo -e "    ${CYAN}logs/dashboard.log${NC}  Frontend"
echo ""
echo -e "  Stop: ${CYAN}bash stop.sh${NC}"
echo ""

# Keep alive — Ctrl+C kills everything
trap "echo -e '\nStopping...'; kill $API_PID $CAPTURE_PID $ANOMALY_PID $CLASSIFIER_PID $RESPONDER_PID $DASH_PID 2>/dev/null; sudo pkill -f sentinel.core.capture.main 2>/dev/null; exit 0" INT TERM
wait $API_PID
