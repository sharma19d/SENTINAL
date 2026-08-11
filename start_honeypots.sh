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
# directory is unwritable *by the container* and Cowrie produces no sessions
# at all. Testing `-w` here was wrong: run.sh is often invoked with sudo, so
# root always passes the test and the fix was skipped — while cowrie inside
# the container runs as uid 1000 and still could not write. Make the mount
# world-writable unconditionally; it holds only honeypot logs.
LOG_DIR="$PROJECT_ROOT/deception/cowrie/log"
CANARY_DIR="$PROJECT_ROOT/deception/opencanary"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
$SUDO mkdir -p "$LOG_DIR" "$CANARY_DIR" 2>/dev/null || true
$SUDO chmod 777 "$LOG_DIR" "$CANARY_DIR" 2>/dev/null || true

# ── Ensure Cowrie emits JSON ─────────────────────────────────────
# The parsers (API + honeypot monitor) read cowrie.json. Without an
# [output_jsonlog] section Cowrie only writes its plain-text log, so every
# attack was captured by the honeypot and then dropped on the floor: no
# sessions in the Honeypots tab, no threat events, no auto-block.
COWRIE_CFG="$PROJECT_ROOT/deception/cowrie/cowrie.cfg"
if [ -f "$COWRIE_CFG" ] && ! grep -q '^\[output_jsonlog\]' "$COWRIE_CFG"; then
  echo -e "  Enabling Cowrie JSON logging…"
  $SUDO tee -a "$COWRIE_CFG" >/dev/null <<'CFGEOF'

[output_jsonlog]
enabled = true
logfile = ${honeypot:log_path}/cowrie.json
CFGEOF
fi

# ── Locate Cowrie's install root inside the image ────────────────
# The mounts were hardcoded to /home/cowrie/cowrie-git, but the official
# cowrie/cowrie image installs to /cowrie/cowrie-git. Docker happily creates
# the wrong path, so the container started "successfully" while Cowrie ran on
# its built-in defaults and wrote logs to an unmounted directory — the honeypot
# captured every attack and the host saw nothing. Ask the image where it lives
# instead of guessing.
COWRIE_HOME="$($DOCKER inspect -f '{{.Config.WorkingDir}}' cowrie/cowrie:latest 2>/dev/null || true)"
case "$COWRIE_HOME" in
  /*cowrie-git) ;;                      # looks right, keep it
  *) COWRIE_HOME="/cowrie/cowrie-git" ;;  # image not pulled yet / odd value
esac
echo -e "  Cowrie install root: ${CYAN}$COWRIE_HOME${NC}"

# ── Generate compose file ────────────────────────────────────────
# Written at runtime with absolute paths and the live subnet, so nothing is
# hardcoded to one network the way deception/docker-compose.yml was.
#
# A previous `sudo bash run.sh` leaves this file owned by root, and a later
# non-root run then fails to overwrite it — `cat >` prints "Permission denied"
# but the script continues and Docker silently starts the STALE compose file,
# so config changes appear to have no effect. Clear it first, and abort the
# honeypot step outright if it is still not writable.
[ -e "$GENERATED_COMPOSE" ] && [ ! -w "$GENERATED_COMPOSE" ] && $SUDO rm -f "$GENERATED_COMPOSE"
if ! : > "$GENERATED_COMPOSE" 2>/dev/null; then
  echo -e "  ${RED}✗ Cannot write $GENERATED_COMPOSE — skipping honeypots.${NC}"
  echo -e "    Fix: sudo rm -f $GENERATED_COMPOSE"
  exit 0
fi
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
      - $PROJECT_ROOT/deception/cowrie/cowrie.cfg:${COWRIE_HOME}/etc/cowrie.cfg:ro
      - $PROJECT_ROOT/deception/cowrie/log:${COWRIE_HOME}/var/log/cowrie
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
      - $PROJECT_ROOT/deception/cowrie/cowrie.cfg:${COWRIE_HOME}/etc/cowrie.cfg:ro
      - $PROJECT_ROOT/deception/cowrie/log:${COWRIE_HOME}/var/log/cowrie
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

# ── Verify Cowrie actually loaded our config ─────────────────────
# A running container proves nothing: with a bad mount path Cowrie starts
# happily on its built-in defaults and logs where the host cannot see. Our
# cowrie.cfg enables telnet and JSON output, neither of which the stock
# config does — so their absence is a precise signal the mount is wrong.
# The image ships no shell, so this is checked from the host: compare the
# container's mount destination against the image's own working directory.
if $DOCKER inspect -f '{{.State.Running}}' sentinel-cowrie 2>/dev/null | grep -q true; then
  IMG_HOME="$($DOCKER inspect -f '{{.Config.WorkingDir}}' cowrie/cowrie:latest 2>/dev/null || true)"
  # One destination per line and an exact (-F -x) match: a substring test
  # passes the broken /home/cowrie/cowrie-git path, since it *ends with* the
  # correct /cowrie/cowrie-git one.
  MOUNTED="$($DOCKER inspect -f '{{range .Mounts}}{{println .Destination}}{{end}}' sentinel-cowrie 2>/dev/null || true)"
  if [ -n "$IMG_HOME" ] && ! printf '%s\n' "$MOUNTED" | grep -Fxq "$IMG_HOME/etc/cowrie.cfg"; then
    echo -e "  ${RED}✗ Config is mounted outside Cowrie's install root ($IMG_HOME)${NC}"
    echo -e "    Cowrie will run on defaults and capture nothing the host can see."
  else
    echo -e "  ${GREEN}✓ Cowrie config mounted at $COWRIE_HOME/etc/cowrie.cfg${NC}"
  fi
fi

if [ "$HONEYPOT_MODE" = "bridge" ]; then
  HOST_IP="$(ip -4 -o addr show "$IFACE" | awk '{print $4}' | cut -d/ -f1 | head -1)"
  echo -e "  ${CYAN}Cowrie SSH${NC}     $HOST_IP:2222"
  echo -e "  ${CYAN}Cowrie Telnet${NC}  $HOST_IP:2223"
  echo -e "  ${CYAN}OpenCanary${NC}     $HOST_IP:8080 (HTTP) 2121 (FTP) 4445 (SMB)"
  echo -e "  Test it:  ${CYAN}ssh -p 2222 root@$HOST_IP${NC}  (any password is accepted)"
fi
