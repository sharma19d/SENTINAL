#!/usr/bin/env bash
# SENTINEL — Stop all services
pkill -f "uvicorn api.main"                2>/dev/null && echo "✓ Backend stopped"            || echo "Backend was not running"
pkill -f "sentinel.core.capture.main"      2>/dev/null && echo "✓ Capture stopped"            || echo "Capture was not running"
sudo pkill -f "sentinel.core.capture.main" 2>/dev/null || true   # in case it ran as root
pkill -f "sentinel.agents.anomaly.worker"  2>/dev/null && echo "✓ Anomaly worker stopped"     || echo "Anomaly worker was not running"
pkill -f "sentinel.agents.classifier.worker" 2>/dev/null && echo "✓ Classifier worker stopped" || echo "Classifier worker was not running"
pkill -f "sentinel.agents.responder.worker"  2>/dev/null && echo "✓ Responder worker stopped"  || echo "Responder worker was not running"
pkill -f "vite.*dashboard"                 2>/dev/null && echo "✓ Dashboard stopped"           || echo "Dashboard was not running"
pkill -f "npm.*dev.*dashboard"             2>/dev/null || true
echo "Done."
