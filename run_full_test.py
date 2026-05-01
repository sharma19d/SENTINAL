
import json
import time
import redis
import sys

def run_integration_test():
    r = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)
    
    # 1. Listener for all relevant channels
    p = r.pubsub()
    p.subscribe('sentinel:anomaly', 'sentinel:threat', 'sentinel:actions', 'sentinel:alerts')
    
    print("--- SENTINEL END-TO-END INTEGRATION TEST (L1 -> L3) ---")
    print("Injecting 10 suspicious packets from dev_aabbccddeeff...")
    
    # 2. Inject Packets (Simulating Layer 1 output)
    # We send 15 packets to ensure the sliding window of 10 is saturated 
    # and the LSTM has enough data to trigger an anomaly.
    for i in range(15):
        pkt = {
            "src": "192.168.1.50",
            "mac_src": "AA:BB:CC:DD:EE:FF",
            "sport": 10000 + i,
            "dst": "185.220.101.12",
            "dport": 443,
            "len": 1200 + (i * 100), # Abnormal increasing length
            "proto": "TCP",
            "ts": time.time()
        }
        r.publish('sentinel:packets', json.dumps(pkt))
        time.sleep(0.1) # Small delay to simulate real traffic
        
    print("Injection complete. Waiting for agents to process...")
    
    # 3. Monitor Results
    timeout = 60 # Gemma 4 can take some time
    start_time = time.time()
    
    results = {
        "anomaly": False,
        "threat": False,
        "action": False
    }
    
    while time.time() - start_time < timeout:
        message = p.get_message()
        if message and message['type'] == 'message':
            channel = message['channel']
            data = json.loads(message['data'])
            
            if channel == 'sentinel:anomaly':
                print(f"\n[AGENT 1] ANOMALY DETECTED!")
                print(f"  Score: {data['anomaly_score']}")
                results["anomaly"] = True
                
            elif channel == 'sentinel:threat':
                print(f"\n[AGENT 2] THREAT CLASSIFIED BY GEMMA 4!")
                print(f"  Tactic: {data['tactic']}")
                print(f"  Technique: {data['technique_id']}")
                print(f"  Severity: {data['severity']}")
                print(f"  Summary: {data['summary']}")
                results["threat"] = True
                
            elif channel == 'sentinel:actions' or channel == 'sentinel:alerts':
                print(f"\n[AGENT 3] RESPONSE PLANNED!")
                if 'action' in data:
                    print(f"  Action: {data['action']}")
                if 'status' in data:
                    print(f"  Status: {data['status']}")
                results["action"] = True
                
        if all(results.values()):
            print("\n✅ FULL PIPELINE SUCCESSFUL!")
            return True
            
        time.sleep(0.1)
    
    print("\n❌ TEST TIMED OUT")
    for step, success in results.items():
        if not success:
            print(f"  - {step.upper()} phase failed to complete.")
    return False

if __name__ == "__main__":
    success = run_integration_test()
    sys.exit(0 if success else 1)
