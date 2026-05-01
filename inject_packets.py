
import redis
import json
import time

r = redis.Redis(host='127.0.0.1', port=6379)
for i in range(12):
    pkt = {
        "src": "192.168.1.50",
        "mac_src": "AA:BB:CC:DD:EE:FF",
        "sport": 1000 + i,
        "dst": "8.8.8.8",
        "dport": 443,
        "len": 500 + i * 100,
        "proto": "TCP",
        "ts": time.time()
    }
    r.publish('sentinel:packets', json.dumps(pkt))
    print(f"Published packet {i+1}")
    time.sleep(0.1)
