
import asyncio
import json
import uuid
import numpy as np
import structlog
from sentinel.agents.anomaly.kitsune import KitsuneExtractor
from sentinel.agents.anomaly.inference import AnomalyDetector
from sentinel.agents.classifier.gemma_client import GemmaClassifier
from sentinel.agents.responder.graph import ResponseGraph
from sentinel.core.fingerprinting.registry import DeviceRegistry
from sentinel.config.settings import settings as app_settings

# Configure logging to console
import logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)
logger = structlog.get_logger()

async def run_sync_integration():
    print("\n" + "="*60)
    print("SENTINEL SYNCHRONOUS INTEGRATION TEST (L1 -> L3)")
    print("="*60)

    # 1. Initialize all components
    extractor = KitsuneExtractor()
    detector = AnomalyDetector()
    classifier = GemmaClassifier()
    responder = ResponseGraph()
    registry = DeviceRegistry(db_url=app_settings.db_url)

    # 2. Prepare mock device in registry
    device_id = "dev_aabbccddeeff"
    registry.upsert_device(
        mac="AA:BB:CC:DD:EE:FF",
        vendor="Hikvision",
        ip="192.168.1.50",
        cve_list=[{"cve_id": "CVE-2021-36260", "score": 9.8}]
    )

    # 3. Step 1: Anomaly Detection (Layer 1 -> Agent 1)
    print("\n[STEP 1] Simulating 10 suspicious packets...")
    window = []
    for i in range(10):
        features = extractor.extract(
            src_ip="192.168.1.50",
            src_mac="AA:BB:CC:DD:EE:FF",
            src_port=1000 + i,
            dst_ip="8.8.8.8",
            dst_mac="00:00:00:00:00:00",
            dst_port=443,
            pkt_len=500 + i * 100,
            timestamp=time.time()
        )
        window.append(features)
    
    score, is_anomaly = detector.predict(np.array(window))
    print(f"  -> Anomaly Score: {score:.6f} (Anomaly: {is_anomaly})")
    
    if not is_anomaly:
        print("❌ Layer 1 Test Failed: No anomaly detected.")
        return

    # 4. Step 2: Threat Classification (Agent 1 -> Agent 2)
    print("\n[STEP 2] Classifying threat with Gemma 4 E2B...")
    # Mock anomaly event
    anomaly_event = {
        "device_id": device_id,
        "src_ip": "192.168.1.50",
        "dst_ip": "8.8.8.8",
        "protocol": "TCP",
        "anomaly_score": score,
        "alert_level": "critical",
        "timestamp": time.time()
    }
    
    # Enrichment
    device = registry.get_device(device_id)
    context = {**anomaly_event, "vendor": device.vendor, "cves": "CVE-2021-36260"}
    
    classification = await classifier.classify(context)
    if not classification:
        print("❌ Layer 2 Test Failed: LLM classification failed.")
        return
        
    print(f"  -> Tactic: {classification.get('tactic')}")
    print(f"  -> Severity: {classification.get('severity')}")
    print(f"  -> Action: {classification.get('recommended_action')}")

    # 5. Step 3: Response Planning (Agent 2 -> Agent 3)
    print("\n[STEP 3] Planning response with LangGraph...")
    threat_event = {
        "event_id": str(uuid.uuid4()),
        "device_id": device_id,
        **classification,
        "indicators": ["8.8.8.8"]
    }
    
    final_state = await responder.run(threat_event)
    print(f"  -> Decision: {final_state['rule_name']}")
    print(f"  -> Final Status: {final_state['status']}")
    print(f"  -> Actions: {final_state['actions']}")

    print("\n" + "="*60)
    print("✅ INTEGRATION TEST SUCCESSFUL")
    print("="*60 + "\n")

if __name__ == "__main__":
    import time
    asyncio.run(run_sync_integration())
