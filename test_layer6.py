
import asyncio
import json
from sentinel.agents.classifier.worker import ClassifierWorker
from sentinel.core.fingerprinting.registry import DeviceRegistry
from sentinel.config.settings import settings as app_settings

async def test_layer6_enrichment():
    print("\n--- SENTINEL LAYER 6 (INTEL BUS) VERIFICATION ---")
    
    # 1. Initialize
    worker = ClassifierWorker()
    registry = DeviceRegistry(db_url=app_settings.db_url)
    
    # Ensure test device exists
    registry.upsert_device(mac="AA:BB:CC:DD:EE:FF", vendor="Hikvision", ip="192.168.1.50")
    
    # 2. Mock Anomaly Event (Targeting a known Tor/Malicious IP)
    anomaly = {
        "device_id": "dev_aabbccddeeff",
        "src_ip": "192.168.1.50",
        "dst_ip": "185.220.101.12",
        "protocol": "TCP",
        "anomaly_score": 0.85,
        "alert_level": "warning",
        "timestamp": 1683100000
    }
    
    print(f"\n[STEP 1] Processing Anomaly targeting {anomaly['dst_ip']}...")
    
    # 3. Process (This will trigger IntelBus lookup)
    # We call the internal method directly for the test
    try:
        # We need to mock the LLM call or just check if intel data is gathered
        # Since we want to verify Layer 6, we'll check the context gathering
        
        print("[STEP 2] Gathering Global Intel via AlienVault OTX...")
        intel_data = await worker.intel_bus.enrich_ip(anomaly["dst_ip"])
        
        print("\nENRICHMENT RESULTS:")
        print(f"  - IP: {intel_data['ip']}")
        print(f"  - OTX Pulses: {intel_data['otx_pulse_count']}")
        print(f"  - Tags: {intel_data['otx_tags']}")
        print(f"  - Abuse Score: {intel_data['abuse_score']}")
        print(f"  - Malicious Flag: {intel_data['is_malicious']}")
        
        if intel_data['otx_pulse_count'] > 0:
            print("\n✅ LAYER 6 VERIFIED: Global threat intelligence successfully retrieved.")
            return True
        else:
            print("\n❌ LAYER 6 FAILED: No intel data retrieved.")
            return False
            
    except Exception as e:
        print(f"❌ Test Error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_layer6_enrichment())
