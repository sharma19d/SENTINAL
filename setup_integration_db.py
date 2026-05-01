
import json
import time
from sentinel.core.fingerprinting.registry import DeviceRegistry
from sentinel.config.settings import settings

def setup_test_db():
    registry = DeviceRegistry(db_url=settings.db_url)
    # Add a vulnerable camera
    registry.upsert_device(
        mac="AA:BB:CC:DD:EE:FF",
        vendor="Hikvision",
        os_guess="Embedded Linux",
        ip="192.168.1.50",
        cve_list=[{"cve_id": "CVE-2021-36260", "score": 9.8, "description": "RCE"}]
    )
    print("Test device 'dev_aabbccddeeff' added to registry.")

if __name__ == "__main__":
    setup_test_db()
