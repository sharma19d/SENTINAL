"""
SENTINEL Agent 1 — Inference Engine

Loads the ONNX model and performs anomaly detection on feature vectors.
"""

import os
import pickle
import numpy as np
import onnxruntime as ort
import structlog
from typing import Tuple, Optional

logger = structlog.get_logger(__name__)

class AnomalyDetector:
    """
    Inference engine for the SENTINEL LSTM Autoencoder.
    """
    def __init__(self, 
                 model_path: str = "sentinel/models/sentinel_lstm.onnx",
                 scaler_path: str = "sentinel/models/sentinel_scaler.pkl",
                 threshold_path: str = "sentinel/models/sentinel_threshold.txt"):
        
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.threshold_path = threshold_path
        
        # Load scaler
        try:
            with open(self.scaler_path, "rb") as f:
                self.scaler = pickle.load(f)
            logger.info("scaler_loaded", path=self.scaler_path)
        except Exception as e:
            logger.error("scaler_load_failed", error=str(e))
            self.scaler = None

        # Load threshold
        try:
            if os.path.exists(self.threshold_path):
                with open(self.threshold_path, "r") as f:
                    self.threshold = float(f.read().strip())
                logger.info("threshold_loaded", threshold=self.threshold)
            else:
                self.threshold = 0.5 # Default fallback
                logger.warning("threshold_file_missing", default=0.5)
        except Exception as e:
            logger.error("threshold_load_failed", error=str(e))
            self.threshold = 0.5

        # Load ONNX model
        try:
            self.session = ort.InferenceSession(self.model_path)
            self.input_name = self.session.get_inputs()[0].name
            logger.info("model_loaded", path=self.model_path)
        except Exception as e:
            logger.error("model_load_failed", error=str(e))
            self.session = None

    def predict(self, feature_sequence: np.ndarray) -> Tuple[float, bool]:
        """
        Perform inference and return anomaly score (MSE) and is_anomaly.
        
        Args:
            feature_sequence: Array of shape (10, 115)
        """
        if self.session is None or self.scaler is None:
            return 0.0, False

        # Scale features
        scaled_features = self.scaler.transform(feature_sequence)
        
        # Prepare for LSTM (batch, seq_len, features) -> (1, 10, 115)
        input_data = scaled_features.reshape(1, 10, -1).astype(np.float32)

        # Inference
        outputs = self.session.run(None, {self.input_name: input_data})
        reconstruction = outputs[0]

        # Calculate Reconstruction Error (MSE) 
        # Usually we care about the reconstruction of the most recent packet (last in sequence)
        # or the average across the sequence.
        mse = np.mean(np.power(input_data - reconstruction, 2))
        
        is_anomaly = mse > self.threshold
        
        return float(mse), bool(is_anomaly)
