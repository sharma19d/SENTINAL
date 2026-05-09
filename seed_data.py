
import redis
import json
import time

r = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)

# 1. Inject Discovery Events
discovery_events = [
    {
        "event_type": "arp",
        "mac_address": "00:11:22:33:44:55",
        "ip_address": "192.168.1.10",
        "vendor": "Samsung Electronics"
    },
    {
        "event_type": "mdns",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "ip_address": "192.168.1.15",
        "mdns_hostname": "Kitchen-Cam.local",
        "vendor": "Hikvision"
    },
    {
        "event_type": "dhcp",
        "mac_address": "11:22:33:44:55:66",
        "ip_address": "192.168.1.20",
        "dhcp_hostname": "Vinay-Laptop",
        "vendor": "Apple Inc."
    }
]

for event in discovery_events:
    r.publish('sentinel:discovery', json.dumps(event))
    print(f"Published discovery event for {event['mac_address']}")
    time.sleep(0.5)

# 2. Inject Flow Events
flow_events = [
    {
        "event_type": "NEW_FLOW",
        "flow": {
            "src_mac": "00:11:22:33:44:55",
            "src_ip": "192.168.1.10",
            "dst_mac": "DE:AD:BE:EF:CA:FE",
            "dst_ip": "8.8.8.8",
            "proto": "TCP",
            "dport": 443
        }
    }
]

for event in flow_events:
    r.publish('sentinel:flows', json.dumps(event))
    print(f"Published flow event for {event['flow']['src_mac']}")
    time.sleep(0.5)

# 3. Inject Threat Alert
threat_event = {
    "channel": "sentinel:threat",
    "data": {
        "event_id": "alert-001",
        "device_id": "mac-001122334455",
        "tactic": "Initial Access",
        "technique_id": "T1190",
        "confidence": 0.95,
        "severity": 8,
        "summary": "Exploit of Vulnerable External-Facing Application",
        "indicators": ["1.2.3.4"],
        "action_taken": "none",
        "timestamp": time.time()
    }
}
r.publish('sentinel:threat', json.dumps(threat_event['data']))
print("Published threat alert")
