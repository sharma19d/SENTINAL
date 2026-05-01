"""
SENTINEL Agent 1 — Anomaly Detection Worker

Subscribes to raw packet events, extracts Kitsune features,
and runs LSTM inference to detect anomalies.
"""

import json
import redis
import structlog
import numpy as np
from typing import Dict
from collections import deque

from sentinel.config.settings import settings as app_settings
from sentinel.agents.anomaly.kitsune import KitsuneExtractor
from sentinel.agents.anomaly.inference import AnomalyDetector

logger = structlog.get_logger(__name__)

class AnomalyWorker:
    """
    Agent 1 Worker: Listen to packets, extract features, predict using sliding window.
    """
    def __init__(self, window_size: int = 10):
        self.redis_client = redis.Redis(
            host=app_settings.redis_host,
            port=app_settings.redis_port,
            db=app_settings.redis_db,
            password=app_settings.redis_password,
            decode_responses=True
        )
        self.pubsub = self.redis_client.pubsub()
        
        # Components
        self.extractor = KitsuneExtractor()
        self.detector = AnomalyDetector()
        
        # State
        self.window_size = window_size
        self.windows: Dict[str, deque] = {} # device_id -> deque of features
        
        # Channels
        self.packet_channel = "sentinel:packets"
        self.anomaly_channel = "sentinel:anomaly"

    def run(self):
        """Main loop to process packets."""
        try:
            self.pubsub.subscribe(self.packet_channel)
            logger.info("anomaly_worker_started", 
                         channel=self.packet_channel,
                         window_size=self.window_size)
            
            for message in self.pubsub.listen():
                if message["type"] == "message":
                    self._process_packet(message["data"])
                    
        except Exception as e:
            logger.error("anomaly_worker_failed", error=str(e))
        finally:
            self.pubsub.unsubscribe()
            logger.info("anomaly_worker_stopped")

    def _process_packet(self, data_str: str):
        """
        Process a single packet event.
        """
        try:
            pkt = json.loads(data_str)
            device_id = pkt.get("mac_src") or pkt["src"]
            
            # 1. Extract features (115)
            features = self.extractor.extract(
                src_ip=pkt["src"],
                src_mac=pkt.get("mac_src", "00:00:00:00:00:00"),
                src_port=pkt.get("sport") or 0,
                dst_ip=pkt["dst"],
                dst_mac="00:00:00:00:00:00",
                dst_port=pkt.get("dport") or 0,
                pkt_len=pkt["len"],
                timestamp=pkt["ts"]
            )
            
            # 2. Update sliding window
            if device_id not in self.windows:
                self.windows[device_id] = deque(maxlen=self.window_size)
            
            self.windows[device_id].append(features)
            
            # 3. Predict only if window is full
            if len(self.windows[device_id]) == self.window_size:
                feature_seq = np.array(list(self.windows[device_id]))
                score, is_anomaly = self.detector.predict(feature_seq)
                
                # LOG EVERY PREDICTION FOR DEBUGGING
                logger.info("prediction", device=device_id, score=score, is_anomaly=is_anomaly)
                
                if is_anomaly:
                    self._report_anomaly(pkt, score, features)
                
        except Exception as e:
            logger.error("packet_processing_error", error=str(e))

    def _report_anomaly(self, pkt: dict, score: float, features: np.ndarray):
        """
        Publish anomaly event to Redis.
        """
        event = {
            "device_id": pkt.get("mac_src") or pkt["src"],
            "src_ip": pkt["src"],
            "dst_ip": pkt["dst"],
            "protocol": pkt.get("proto"),
            "anomaly_score": round(score, 6),
            "alert_level": "critical" if score > self.detector.threshold * 2 else "warning",
            "feature_vector": features.tolist(), # Optional: for downstream classifier context
            "timestamp": pkt["ts"]
        }
        
        self.redis_client.publish(self.anomaly_channel, json.dumps(event))
        logger.warning("anomaly_detected", 
                        device=event["device_id"], 
                        score=score,
                        dst=pkt["dst"])

if __name__ == "__main__":
    worker = AnomalyWorker()
    worker.run()
