#!/usr/bin/env bash
# SENTINEL — Stop all services

CAPTURE_PATTERN="sentinel.core.capture.main"

kill_pattern() {
  local pattern="$1" label="$2"
  if pkill -f "$pattern" 2>/dev/null; then
    echo "✓ $label stopped"
  else
    echo "  $label was not running"
  fi
}

kill_pattern "uvicorn api.main"                  "Backend"
kill_pattern "sentinel.agents.anomaly.worker"    "Anomaly worker"
kill_pattern "sentinel.agents.classifier.worker" "Classifier worker"
kill_pattern "sentinel.agents.responder.worker"  "Responder worker"
kill_pattern "sentinel.agents.honeypot.worker"   "Honeypot monitor"
kill_pattern "sentinel.core.fingerprinting.discovery" "Discovery agent"

# Vite is launched as `vite --port=3000`, so a "vite.*dashboard" pattern
# never matches its command line. Match the actual invocation instead.
kill_pattern "[v]ite --port=3000" "Dashboard"

# ── Capture engine (runs as root under sudo) ─────────────────────
# Non-root pkill cannot signal root-owned processes, and a bare `sudo pkill`
# in a non-interactive shell fails silently. Both of those let old capture
# engines survive every restart and pile up, all writing to the same DB.
pkill -f "$CAPTURE_PATTERN" 2>/dev/null || true
sleep 0.5

if pgrep -f "$CAPTURE_PATTERN" >/dev/null 2>&1; then
  if sudo -n true 2>/dev/null; then
    sudo pkill -f "$CAPTURE_PATTERN" 2>/dev/null || true
  else
    echo "  Capture engine is running as root — sudo password required:"
    sudo pkill -f "$CAPTURE_PATTERN" 2>/dev/null || true
  fi
  sleep 0.5
fi

# Escalate to SIGKILL for anything that ignored SIGTERM
if pgrep -f "$CAPTURE_PATTERN" >/dev/null 2>&1; then
  sudo pkill -9 -f "$CAPTURE_PATTERN" 2>/dev/null || true
  sleep 0.5
fi

# ── Honeypot containers (Layer 4) ────────────────────────────────
# They use restart:unless-stopped, so they must be stopped explicitly or
# they survive reboots and keep holding their ports.
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="sudo docker"; fi
  if $DOCKER ps -q -f name=sentinel-cowrie -f name=sentinel-opencanary 2>/dev/null | grep -q .; then
    $DOCKER stop sentinel-cowrie sentinel-opencanary >/dev/null 2>&1 \
      && echo "✓ Honeypots stopped" || echo "  Honeypots could not be stopped"
  else
    echo "  Honeypots were not running"
  fi
fi

REMAINING=$(pgrep -cf "$CAPTURE_PATTERN" 2>/dev/null); REMAINING=${REMAINING:-0}
if [ "$REMAINING" -eq 0 ]; then
  echo "✓ Capture stopped"
else
  echo "✗ WARNING: $REMAINING capture process(es) still running."
  echo "  Kill manually:  sudo pkill -9 -f $CAPTURE_PATTERN"
fi

echo "Done."
