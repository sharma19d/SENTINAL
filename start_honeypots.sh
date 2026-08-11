#!/usr/bin/env bash
# SENTINEL — Layer 4 Honeypot Deployment
#
# Brings up Cowrie and OpenCanary. Called automatically by run.sh so the
# deception layer starts with the rest of the system rather than needing a
# separate manual step.
#
# Two deployment modes:
#
#   macvlan  — each honeypot gets its own LAN IP and appears as a distinct
#              device. Requires the parent interface to carry multiple
#              source MACs, which only works on a wired link or the Pi 5
#              bridge deployment.
#
#   bridge   — honeypots share the host IP on mapped ports. Works anywhere,
#              including a Wi-Fi adapter in managed mode, where macvlan
#              cannot work at all (802.11 associates one MAC per station,
#              so the AP drops frames from the extra macvlan MACs).
#
# Mode is chosen automatically from the capture interface; override with
# HONEYPOT_MODE=macvlan|bridge. Skip entirely with HONEYPOT_ENABLED=false.

set -uo pipefail
cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

HONEYPOT_ENABLED="${HONEYPOT_ENABLED:-true}"
GENERATED_COMPOSE="$PROJECT_ROOT/.honeypots.generated.yml"

if [ "$HONEYPOT_ENABLED" != "true" ]; then
  echo -e "  ${YELLOW}Honeypots disabled (HONEYPOT_ENABLED=false)${NC}"
  exit 0
fi

# ── Docker availability ──────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo -e "  ${YELLOW}Docker not installed — skipping honeypots.${NC}"
  echo -e "  Layer 4 will report OFFLINE in the dashboard."
  exit 0
fi

# Honeypots bind privileged-ish ports and manage networks, and this user is
# typically not in the docker group, so determine how to invoke docker once.
if docker info >/dev/null 2>&1; then
  DOCKER="docker"
elif sudo -n docker info >/dev/null 2>&1; then
  DOCKER="sudo docker"
else
  echo -e "  ${YELLOW}Docker needs sudo (password required).${NC}"
  if sudo docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
  else
    echo -e "  ${RED}✗ Cannot reach the Docker daemon — skipping honeypots.${NC}"
    exit 0
  fi
fi

# ── Detect network + choose mode ─────────────────────────────────
IFACE="$(ip -4 route show default 2>/dev/null | awk '/default via/ {print $5; exit}')"
IFACE="${IFACE:-wlan0}"

if [ -z "${HONEYPOT_MODE:-}" ]; then
  # `iw dev <iface> info` only succeeds for wireless interfaces.
  if iw dev "$IFACE" info >/dev/null 2>&1; then
    HONEYPOT_MODE="bridge"
    MODE_REASON="$IFACE is wireless; macvlan cannot pass traffic in managed mode"
  else
    HONEYPOT_MODE="macvlan"
    MODE_REASON="$IFACE is wired; honeypots can hold their own LAN IPs"
  fi
else
  MODE_REASON="forced via HONEYPOT_MODE"
fi

echo -e "  Interface: ${CYAN}$IFACE${NC}  Mode: ${CYAN}$HONEYPOT_MODE${NC}"
echo -e "  ${MODE_REASON}"

# ── Ensure Cowrie can write its logs ─────────────────────────────
# deception/ is root-owned in a fresh checkout, so the bind-mounted log
# directory is unwritable and Cowrie produces no sessions at all.
LOG_DIR="$PROJECT_ROOT/deception/cowrie/log"
if [ ! -d "$LOG_DIR" ] || [ ! -w "$LOG_DIR" ]; then
  echo -e "  Fixing honeypot log permissions…"
  sudo mkdir -p "$LOG_DIR" "$PROJECT_ROOT/deception/opencanary"
  sudo chown -R "$(id -u):$(id -g)" "$PROJECT_ROOT/deception"
fi

# ── Generate compose file ────────────────────────────────────────
# Written at runtime with absolute paths and the live subnet, so nothing is
# hardcoded to one network the way deception/docker-compose.yml was.
if [ "$HONEYPOT_MODE" = "bridge" ]; then
  cat > "$GENERATED_COMPOSE" <<EOF
services:
  cowrie:
    image: cowrie/cowrie:latest
    container_name: sentinel-cowrie
    restart: unless-stopped
    ports:
      - "2222:2222"
      - "2223:2223"
    volumes:
      - $PROJECT_ROOT/deception/cowrie/cowrie.cfg:/home/cowrie/cowrie-git/etc/cowrie.cfg:ro
      - $PROJECT_ROOT/deception/cowrie/log:/home/cowrie/cowrie-git/var/log/cowrie
    environment:
      - TZ=UTC

  opencanary:
    image: thinkst/opencanary:latest
    container_name: sentinel-opencanary
    restart: unless-stopped
    ports:
      - "8080:80"
      - "2121:21"
      - "4445:445"
      - "33306:3306"
    volumes:
      - $PROJECT_ROOT/deception/opencanary/opencanary.conf:/root/.opencanary.conf:ro
      - $PROJECT_ROOT/deception/opencanary:/var/log
    environment:
      - TZ=UTC
EOF
else
  SUBNET="$(ip -4 -o addr show "$IFACE" | awk '{print $4}' | head -1)"
  GATEWAY="$(ip -4 route show default | awk '/default via/ {print $3; exit}')"
  BASE="$(echo "$SUBNET" | cut -d/ -f1 | cut -d. -f1-3)"
  NETCIDR="${BASE}.0/24"

  cat > "$GENERATED_COMPOSE" <<EOF
services:
  cowrie:
    image: cowrie/cowrie:latest
    container_name: sentinel-cowrie
    restart: unless-stopped
    networks:
      honeypot-net:
        ipv4_address: ${BASE}.201
    volumes:
      - $PROJECT_ROOT/deception/cowrie/cowrie.cfg:/home/cowrie/cowrie-git/etc/cowrie.cfg:ro
      - $PROJECT_ROOT/deception/cowrie/log:/home/cowrie/cowrie-git/var/log/cowrie
    environment:
      - TZ=UTC

  opencanary:
    image: thinkst/opencanary:latest
    container_name: sentinel-opencanary
    restart: unless-stopped
    networks:
      honeypot-net:
        ipv4_address: ${BASE}.202
    volumes:
      - $PROJECT_ROOT/deception/opencanary/opencanary.conf:/root/.opencanary.conf:ro
      - $PROJECT_ROOT/deception/opencanary:/var/log
    environment:
      - TZ=UTC

networks:
  honeypot-net:
    driver: macvlan
    driver_opts:
      parent: $IFACE
    ipam:
      config:
        - subnet: $NETCIDR
          gateway: $GATEWAY
          ip_range: ${BASE}.200/29
EOF
fi

# ── Clear stale containers ───────────────────────────────────────
# Containers from a previous run (or the old deception/docker-compose.yml)
# keep the names sentinel-cowrie / sentinel-opencanary, and `compose up`
# refuses to reuse a name held by a container it didn't create. Remove any
# stragglers first so startup is idempotent.
for c in sentinel-cowrie sentinel-opencanary; do
  if $DOCKER inspect "$c" >/dev/null 2>&1; then
    $DOCKER rm -f "$c" >/dev/null 2>&1 && echo -e "  Removed stale container: $c"
  fi
done

# ── Start ────────────────────────────────────────────────────────
echo -e "  Starting honeypot containers (first run pulls images, may take a few minutes)…"

if ! $DOCKER compose -f "$GENERATED_COMPOSE" up -d 2>&1 | tail -5; then
  echo -e "  ${RED}✗ Honeypot startup failed.${NC}"
  echo -e "  Retry manually: $DOCKER compose -f $GENERATED_COMPOSE up -d"
  exit 0   # never block the rest of the system
fi

sleep 3

for c in sentinel-cowrie sentinel-opencanary; do
  state="$($DOCKER inspect -f '{{.State.Running}}' "$c" 2>/dev/null)"
  if [ "$state" = "true" ]; then
    echo -e "  ${GREEN}✓ $c running${NC}"
  else
    echo -e "  ${RED}✗ $c not running${NC}  (logs: $DOCKER logs $c)"
  fi
done

if [ "$HONEYPOT_MODE" = "bridge" ]; then
  HOST_IP="$(ip -4 -o addr show "$IFACE" | awk '{print $4}' | cut -d/ -f1 | head -1)"
  echo -e "  ${CYAN}Cowrie SSH${NC}     $HOST_IP:2222"
  echo -e "  ${CYAN}Cowrie Telnet${NC}  $HOST_IP:2223"
  echo -e "  ${CYAN}OpenCanary${NC}     $HOST_IP:8080 (HTTP) 2121 (FTP) 4445 (SMB)"
  echo -e "  Test it:  ${CYAN}ssh -p 2222 root@$HOST_IP${NC}  (any password is accepted)"
fi
