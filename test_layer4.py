
import json
import time
import subprocess
import redis
import sys

def run_layer4_test():
    r = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)
    
    print("--- SENTINEL LAYER 4 (DECEPTION) VERIFICATION ---")
    
    # 1. Check if Honeypots are up
    print("\n[STEP 1] Checking Honeypot Containers...")
    ps = subprocess.run(["docker", "ps", "--format", "{{.Names}} {{.Status}}"], capture_output=True, text=True)
    containers = ps.stdout.lower()
    
    cowrie_up = "sentinel-cowrie up" in containers
    canary_up = "sentinel-opencanary up" in containers
    
    if cowrie_up and canary_up:
        print("✅ Cowrie and OpenCanary are RUNNING.")
    else:
        print(f"❌ Honeypot containers missing or down.\n{containers}")
        return False

    # 2. Trigger Redirection
    print("\n[STEP 2] Triggering AI-driven Redirection Action...")
    test_attacker = "192.168.0.99"
    test_victim_mac = "AA:BB:CC:DD:EE:FF" # Hikvision in our DB
    test_victim_ip = "192.168.1.50"
    
    action = {
        "event_id": "test-verif-L4",
        "device_id": "dev_aabbccddeeff",
        "action": "redirect_to_honeypot",
        "indicators": [test_attacker]
    }
    
    r.publish('sentinel:actions', json.dumps(action))
    print(f"  -> Published redirect action for attacker {test_attacker} targeting {test_victim_ip}")
    
    time.sleep(2) # Give daemon time to inject rule

    # 3. Verify Nftables Rules
    print("\n[STEP 3] Verifying Kernel-Level Nftables Rules...")
    nft = subprocess.run(["nft", "list", "table", "inet", "sentinel"], capture_output=True, text=True)
    rules = nft.stdout
    
    dnat_exists = f"ip saddr {test_attacker} ip daddr {test_victim_ip} dnat ip to 192.168.0.202" in rules
    masq_exists = f"ip saddr {test_attacker} ip daddr 192.168.0.202 masquerade" in rules
    
    if dnat_exists and masq_exists:
        print("✅ Nftables DNAT and Masquerade rules are ACTIVE in the kernel.")
    else:
        print("❌ Nftables rules missing.")
        print("DEBUG OUTPUT:")
        print(rules)
        return False

    # 4. Check Honeypot Accessibility (via macvlan bridge)
    # Note: This only works if macvlan_setup.sh was run, but we can at least check if the interface exists
    print("\n[STEP 4] Checking Honeypot Network Connectivity...")
    ip_link = subprocess.run(["ip", "link", "show", "sentinel-br"], capture_output=True, text=True)
    if "sentinel-br" in ip_link.stdout:
        print("✅ Macvlan bridge 'sentinel-br' is CONFIGURED.")
        # Try a quick ping to OpenCanary
        ping = subprocess.run(["ping", "-c", "1", "-W", "1", "192.168.0.202"], capture_output=True)
        if ping.returncode == 0:
            print("✅ Honeypot (192.168.0.202) is REACHABLE from the host.")
        else:
            print("⚠️ Honeypot is up but not reachable from host (standard macvlan behavior without bridge config).")
    else:
        print("⚠️ Macvlan host bridge 'sentinel-br' not found. (Expected if not run yet).")

    print("\n" + "="*40)
    print("✅ LAYER 4 VERIFICATION SUCCESSFUL")
    print("="*40)
    return True

if __name__ == "__main__":
    success = run_layer4_test()
    sys.exit(0 if success else 1)
