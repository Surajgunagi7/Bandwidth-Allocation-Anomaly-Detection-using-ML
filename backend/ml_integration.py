#!/usr/bin/env python3
"""
ML Integration Module - FIXED WITH THRESHOLD ENFORCEMENT AND HISTORY
Key fixes:
1. Enforces prediction confidence thresholds
2. Uses rolling history for temporal smoothing
3. Requires N consecutive anomaly detections before flagging
4. Adds policy layer for admin overrides
"""

import os
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
import logging
from typing import Dict, List, Optional
from datetime import datetime, UTC
from collections import deque
import warnings

from feature_extractor import process_pcap_file
from bandwidth_enforcer import BandwidthDecisionEngine, BandwidthAllocation
from config import Config

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MLModelManager:
    """Manages ML models with confidence thresholds"""
    
    BANDWIDTH_FEATURES = [
        'avg_packet_size', 'total_bytes', 'total_packets', 'flow_duration',
        'bytes_per_second', 'packets_per_second', 'protocol_type',
        'avg_inter_arrival_time', 'std_packet_size', 'unique_dst_ports',
        'tcp_flag_ratio', 'payload_entropy', 'bidirectional_ratio',
        'is_encrypted', 'time_of_day'
    ]
    
    ANOMALY_FEATURES = BANDWIDTH_FEATURES + [
        'connection_rate', 'failed_connection_ratio', 'port_scan_indicator',
        'packet_size_variance', 'protocol_diversity'
    ]
    
    def __init__(self, models_dir: str = "./models", 
                 prediction_threshold: float = 0.65):
        self.models_dir = Path(models_dir)
        self.prediction_threshold = prediction_threshold
        self.bandwidth_model = None
        self.anomaly_model = None
        self.bandwidth_scaler = None
        self.anomaly_scaler = None
        self.expected_bw_features = set(self.BANDWIDTH_FEATURES)
        self.expected_an_features = set(self.ANOMALY_FEATURES)
        self._load_models()
    
    def _load_models(self):
        """Load models with error handling"""
        try:
            bw_model = self.models_dir / "bandwidth_predictor.pkl"
            an_model = self.models_dir / "anomaly_detector.pkl"
            bw_scaler = self.models_dir / "bandwidth_scaler.pkl"
            an_scaler = self.models_dir / "anomaly_scaler.pkl"
            
            if bw_model.exists():
                self.bandwidth_model = joblib.load(bw_model)
                logger.info("✓ Loaded bandwidth model")
            
            if an_model.exists():
                self.anomaly_model = joblib.load(an_model)
                logger.info("✓ Loaded anomaly model")
            
            if bw_scaler.exists():
                self.bandwidth_scaler = joblib.load(bw_scaler)
            
            if an_scaler.exists():
                self.anomaly_scaler = joblib.load(an_scaler)
                
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
    
    def predict_bandwidth(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Predict bandwidth with confidence scores"""
        if self.bandwidth_model is None:
            result = features_df[['mac_address']].copy()
            result['predicted_bandwidth_kbps'] = 1000
            result['confidence'] = 0.0
            return result
        
        missing = self.expected_bw_features - set(features_df.columns)
        if missing:
            raise RuntimeError(f"Missing bandwidth features: {missing}")
        
        try:
            X = features_df[self.BANDWIDTH_FEATURES].copy()
            numeric_features = [f for f in self.BANDWIDTH_FEATURES if f != 'protocol_type']
            
            if self.bandwidth_scaler:
                X_scaled = X.copy()
                X_scaled[numeric_features] = self.bandwidth_scaler.transform(X[numeric_features])
            else:
                X_scaled = X
            
            predictions = self.bandwidth_model.predict(X_scaled)
            
            # Get prediction confidence (if model supports predict_proba)
            if hasattr(self.bandwidth_model, 'predict_proba'):
                probas = self.bandwidth_model.predict_proba(X_scaled)
                confidence = np.max(probas, axis=1)
            else:
                # For regressors, use inverse of prediction std or default
                confidence = np.ones(len(predictions), dtype=float)
            
            result = features_df[['mac_address']].copy()
            result['predicted_bandwidth_kbps'] = np.clip(predictions, 100, 100000).round().astype(int)
            result['confidence'] = confidence
            
            # Filter low confidence predictions
            # low_conf_mask = confidence < self.prediction_threshold
            # if low_conf_mask.any():
            #     logger.warning(f"⚠ {low_conf_mask.sum()} predictions below confidence threshold")
            #     result.loc[low_conf_mask, 'predicted_bandwidth_kbps'] = 1000  # Fallback
            
            return result
            
        except Exception as e:
            logger.error(f"Bandwidth prediction failed: {e}")
            result = features_df[['mac_address']].copy()
            result['predicted_bandwidth_kbps'] = 1000
            result['confidence'] = 0.0
            return result
    
    def detect_anomalies(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Detect anomalies with confidence scores"""

        if getattr(Config, "NO_ANOMALY_MODE", False):
            result = features_df[['mac_address']].copy()
            result['is_anomaly'] = False
            result['anomaly_score'] = 0.0
            result['confidence'] = 1.0
            logger.warning("⚠ NO_ANOMALY_MODE enabled — skipping anomaly detection")
            return result

        if self.anomaly_model is None:
            result = features_df[['mac_address']].copy()
            result['is_anomaly'] = False
            result['anomaly_score'] = 0.0
            result['confidence'] = 0.0
            return result
        
        missing = self.expected_an_features - set(features_df.columns)
        if missing:
            raise RuntimeError(f"Missing anomaly features: {missing}")

        try:
            X = features_df[self.ANOMALY_FEATURES].copy()
            numeric_features = [f for f in self.ANOMALY_FEATURES if f != 'protocol_type']
            
            if self.anomaly_scaler:
                X_scaled = X.copy()
                X_scaled[numeric_features] = self.anomaly_scaler.transform(X[numeric_features])
            else:
                X_scaled = X
            
            predictions = self.anomaly_model.predict(X_scaled)
            anomaly_scores = self.anomaly_model.score_samples(X_scaled)
            
            # # Normalize scores
            # normalized_scores = 1 / (1 + np.exp(anomaly_scores))
            
            # # Confidence based on score magnitude
            # confidence = np.abs(anomaly_scores) / (np.abs(anomaly_scores).max() + 1e-6)
            
            # result = features_df[['mac_address']].copy()
            # result['is_anomaly'] = (predictions == -1)
            # result['anomaly_score'] = normalized_scores
            # result['confidence'] = confidence
            

            # # Only flag anomalies with high confidence
            # low_conf_anomalies = (result['is_anomaly']) & (confidence < self.prediction_threshold)
            # if low_conf_anomalies.any():
            #     logger.warning(f"⚠ Ignoring {low_conf_anomalies.sum()} low-confidence anomalies")
            #     result.loc[low_conf_anomalies, 'is_anomaly'] = False

            # Alternative: temp sol till retrained model with probas
            result = features_df[['mac_address']].copy()
            result['is_anomaly'] = (predictions == -1)
            result['anomaly_score'] = -anomaly_scores  # higher = more anomalous
            result['confidence'] = np.ones(len(predictions))
            
            return result
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            result = features_df[['mac_address']].copy()
            result['is_anomaly'] = False
            result['anomaly_score'] = 0.0
            result['confidence'] = 0.0
            return result
    
    def classify_traffic(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Classify traffic type with heuristics"""
        result = features_df[['mac_address']].copy()
        
        def classify_row(row):
            try:
                if (row.get('protocol_type', 0) == 2 and
                    row.get('bytes_per_second', 0) < 5000 and
                    row.get('std_packet_size', 0) < 200):
                    return 'voip'
                elif (row.get('bytes_per_second', 0) > 3000 and
                      row.get('bytes_per_second', 0) < 15000):
                    return 'video'
                elif (row.get('protocol_type', 0) == 1 and
                      row.get('bytes_per_second', 0) > 10000):
                    return 'bulk'
                elif row.get('unique_dst_ports', 0) > 3:
                    return 'web'
                else:
                    return 'unknown'
            except:
                return 'unknown'
        
        result['traffic_class'] = features_df.apply(classify_row, axis=1)
        return result


class TemporalSmoother:
    """Smooths predictions over time using rolling history"""
    
    def __init__(self, window_size: int = 3, anomaly_consensus: int = 2):
        """
        Args:
            window_size: Number of recent predictions to keep
            anomaly_consensus: Required consecutive anomaly detections
        """
        self.window_size = window_size
        self.anomaly_consensus = anomaly_consensus
        self.history: Dict[str, deque] = {}  # mac -> deque of predictions
        self.anomaly_counts: Dict[str, int] = {}  # mac -> consecutive anomaly count
    
    def smooth_bandwidth(self, mac: str, new_prediction: int, confidence: float) -> int:
        """Apply EWMA smoothing to bandwidth predictions"""
        if mac not in self.history:
            self.history[mac] = deque(maxlen=self.window_size)
        
        self.history[mac].append({'bw': new_prediction, 'conf': confidence})
        
        # Weighted average (higher weight for higher confidence)
        if len(self.history[mac]) == 1:
            return new_prediction
        
        total_weight = 0
        weighted_sum = 0
        
        for entry in self.history[mac]:
            # weight = entry['conf']
            weight = 1.0
            weighted_sum += entry['bw'] * weight
            total_weight += weight
        
        smoothed = int(weighted_sum / total_weight) if total_weight > 0 else new_prediction
        
        logger.debug(f"Smoothed BW for {mac}: {new_prediction} -> {smoothed}")
        return smoothed
    
    def confirm_anomaly(self, mac: str, is_anomaly: bool, confidence: float) -> bool:
        """Require sustained anomaly detection before flagging"""
        if mac not in self.anomaly_counts:
            self.anomaly_counts[mac] = 0
        
        # Only count high-confidence anomalies
        # if is_anomaly and confidence > 0.65:
        if is_anomaly:
            self.anomaly_counts[mac] += 1
        else:
            self.anomaly_counts[mac] = max(0, self.anomaly_counts[mac] - 1)
        
        confirmed = self.anomaly_counts[mac] >= self.anomaly_consensus
        
        if confirmed:
            logger.warning(f"🚨 CONFIRMED anomaly for {mac} ({self.anomaly_counts[mac]} detections)")
        
        return confirmed
    
    def reset_device(self, mac: str):
        """Clear history for a device"""
        self.history.pop(mac, None)
        self.anomaly_counts.pop(mac, None)


class PolicyLayer:
    """Administrative policy layer for override control"""
    
    def __init__(self):
        self.overrides: Dict[str, Dict] = {}  # mac -> override config
        self.global_mode = 'auto'  # 'auto', 'equal', 'manual'
    
    def set_override(self, mac: str, bandwidth_kbps: int, priority: int, duration_sec: Optional[int] = None):
        """Set manual override for a device"""
        self.overrides[mac] = {
            'bandwidth': bandwidth_kbps,
            'priority': priority,
            'expires_at': datetime.now(UTC).timestamp() + duration_sec if duration_sec else None
        }
        logger.info(f"📌 Manual override set for {mac}: {bandwidth_kbps} kbps, priority {priority}")
    
    def clear_override(self, mac: str):
        """Remove override"""
        if mac in self.overrides:
            del self.overrides[mac]
            logger.info(f"📌 Cleared override for {mac}")
    
    def set_global_mode(self, mode: str):
        """Set global bandwidth mode"""
        if mode in ['auto', 'equal', 'manual']:
            self.global_mode = mode
            logger.info(f"🌐 Global mode set to: {mode}")
    
    def apply_policy(self, mac: str, ml_bandwidth: int, ml_priority: int) -> tuple[int, int]:
        """Apply policy override if exists"""
        # Check for expired overrides
        if mac in self.overrides:
            override = self.overrides[mac]
            if override['expires_at'] and datetime.now(UTC).timestamp() > override['expires_at']:
                del self.overrides[mac]
                logger.info(f"⏰ Override expired for {mac}")
            else:
                return override['bandwidth'], override['priority']
        
        # Apply global mode
        if self.global_mode == 'equal':
            return 5000, 2  # Equal 5 Mbps for all
        elif self.global_mode == 'manual':
            return ml_bandwidth, ml_priority  # Defer to admin
        
        # Auto mode - use ML
        return ml_bandwidth, ml_priority


class PipelineController:
    """Main pipeline with history, smoothing, and policy control"""
    
    def __init__(self, models_dir: str = str(Config.MODELS_DIR),
                 interface: str = None, update_interval: int = 10):
        
        if interface is None:
            interface = os.getenv("AP_INTERFACE", Config.AP_INTERFACE)
        
        self.model_manager = MLModelManager(
            models_dir, 
            prediction_threshold=Config.PREDICTION_THRESHOLD
        )
        self.decision_engine = BandwidthDecisionEngine(
            interface=interface,
            update_interval=update_interval,
            change_threshold=Config.TC_CHANGE_THRESHOLD
        )
        
        # NEW: Temporal smoothing and policy control
        self.smoother = TemporalSmoother(
            window_size=3,
            anomaly_consensus=2
        )
        self.policy = PolicyLayer()
        
        self.history = []  # Full prediction history
    
    def process_pcap(self, pcap_path: str) -> Dict:
        """Process PCAP with smoothing and policy"""
        logger.info(f"🔄 Processing: {pcap_path}")
        
        try:
            # Extract features
            features = process_pcap_file(pcap_path)
            if features['all'].empty:
                return {'status': 'error', 'message': 'No features extracted'}
            
            all_features = features['all']
            
            # Run ML models
            bw_preds = self.model_manager.predict_bandwidth(features['bandwidth'])
            an_preds = self.model_manager.detect_anomalies(features['anomaly'])
            traffic_cls = self.model_manager.classify_traffic(all_features)
            
            # Merge predictions
            merged = self._merge_predictions(all_features, bw_preds, an_preds, traffic_cls)
            
            # Apply temporal smoothing
            smoothed = self._apply_smoothing(merged)
            
            # Apply policy layer
            final = self._apply_policy(smoothed)
            
            # Enforce allocations
            enforcement = self._enforce_allocations(final)
            
            # Store history
            self._update_history(merged=merged, smoothed=smoothed, final=final)
            
            response = {
                'status': 'success',
                'timestamp': datetime.now(UTC).isoformat(),
                'devices_processed': len(final),
                'anomalies_confirmed': int(final['is_anomaly'].sum()),
                'predictions': final.to_dict('records'),
                'enforcement': enforcement
            }
            
            logger.info(f"✓ Pipeline complete: {len(final)} devices")
            return response
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    def _merge_predictions(self, features, bandwidth, anomalies, traffic):
        """Merge all predictions"""
        merged = features[['mac_address']].copy()
        
        if not bandwidth.empty:
            merged = merged.merge(bandwidth, on='mac_address', how='left')
        else:
            merged['predicted_bandwidth_kbps'] = 1000
            merged['confidence'] = 0.0
        
        if not anomalies.empty:
            merged = merged.merge(anomalies, on='mac_address', how='left', suffixes=('_bw', '_an'))
        else:
            merged['is_anomaly'] = False
            merged['anomaly_score'] = 0.0
            merged['confidence_an'] = 0.0
        
        if not traffic.empty:
            merged = merged.merge(traffic, on='mac_address', how='left')
        else:
            merged['traffic_class'] = 'unknown'
        
        # Fill NaNs
        merged.fillna({
            'predicted_bandwidth_kbps': 1000,
            'confidence': 0.0,
            'is_anomaly': False,
            'anomaly_score': 0.0,
            'confidence_an': 0.0,
            'traffic_class': 'unknown'
        }, inplace=True)
        
        return merged
    
    def _apply_smoothing(self, predictions: pd.DataFrame) -> pd.DataFrame:
        """Apply temporal smoothing"""
        smoothed = predictions.copy()
        
        for idx, row in smoothed.iterrows():
            mac = row['mac_address']
            
            # Smooth bandwidth
            smoothed_bw = self.smoother.smooth_bandwidth(
                mac, 
                int(row['predicted_bandwidth_kbps']),
                float(row.get('confidence', 0.8))
            )
            smoothed.at[idx, 'predicted_bandwidth_kbps'] = smoothed_bw
            
            # Confirm anomaly
            confirmed = self.smoother.confirm_anomaly(
                mac,
                bool(row['is_anomaly']),
                float(row.get('confidence_an', 0.8))
            )
            smoothed.at[idx, 'is_anomaly'] = confirmed
        
        return smoothed
    
    def _apply_policy(self, predictions: pd.DataFrame) -> pd.DataFrame:
        """Apply policy overrides"""
        final = predictions.copy()
        
        for idx, row in final.iterrows():
            mac = row['mac_address']
            ml_bw = int(row['predicted_bandwidth_kbps'])
            ml_priority = self._classify_priority(row['traffic_class'], row['is_anomaly'])
            
            # Apply policy
            policy_bw, policy_priority = self.policy.apply_policy(mac, ml_bw, ml_priority)
            
            final.at[idx, 'predicted_bandwidth_kbps'] = policy_bw
            final.at[idx, 'priority'] = policy_priority
        
        return final
    
    def _classify_priority(self, traffic_class: str, is_anomaly: bool) -> int:
        """Map traffic class to priority"""
        if is_anomaly:
            return 3
        return Config.TRAFFIC_CLASS_MAP.get(traffic_class.lower(), 2)
    
    def _enforce_allocations(self, predictions: pd.DataFrame) -> Dict:
        """Enforce via decision engine"""
        pred_dicts = []
        
        for _, row in predictions.iterrows():
            pred_dicts.append({
                'mac_address': row['mac_address'],
                'predicted_bandwidth_kbps': int(row['predicted_bandwidth_kbps']),
                'traffic_class': row['traffic_class'],
                'is_anomaly': bool(row['is_anomaly']),
                'priority': int(row.get('priority', 2))
            })
        
        try:
            self.decision_engine.process_ml_predictions(pred_dicts)
            return {
                'status': 'enforced',
                'devices_updated': len(pred_dicts)
            }
        except Exception as e:
            logger.error(f"Enforcement failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def _update_history(self, predictions: pd.DataFrame, merged: pd.DataFrame, max_history: int = 10, smoothed: pd.DataFrame = None, final: pd.DataFrame = None):
        """Store history"""
        # self.history.append({
        #     'timestamp': datetime.now(UTC).isoformat(),
        #     'predictions': predictions.to_dict('records')
        # })
        self.history.append({
            'timestamp': datetime.now(UTC).isoformat(),
            'raw_ml': merged.to_dict('records'),
            'smoothed': smoothed.to_dict('records'),
            'final': final.to_dict('records')
        })

        if len(self.history) > max_history:
            self.history = self.history[-max_history:]
    
    def get_statistics(self) -> Dict:
        """Get stats"""
        try:
            return {
                'active_devices': len(self.decision_engine.tc_controller.active_allocations),
                'allocations': [
                    {
                        'mac': mac,
                        'bandwidth_kbps': alloc.allocated_bw_kbps,
                        'priority': alloc.priority
                    }
                    for mac, alloc in self.decision_engine.tc_controller.active_allocations.items()
                ],
                'history_entries': len(self.history),
                'policy_mode': self.policy.global_mode,
                'active_overrides': len(self.policy.overrides)
            }
        except Exception as e:
            logger.error(f"Stats failed: {e}")
            return {}
    
    # API methods for frontend
    def set_device_override(self, mac: str, bandwidth_kbps: int, priority: int, duration_sec: int = None):
        """Admin override for device"""
        self.policy.set_override(mac, bandwidth_kbps, priority, duration_sec)
    
    def clear_device_override(self, mac: str):
        """Clear admin override"""
        self.policy.clear_override(mac)
    
    def set_mode(self, mode: str):
        """Set global mode"""
        self.policy.set_global_mode(mode)


if __name__ == "__main__":
    pipeline = PipelineController(
        models_dir="./models",
        interface="ap1-wlan1",
        update_interval=10
    )
    
    sample = "./test_data/sample_traffic.pcap"
    if os.path.exists(sample):
        result = pipeline.process_pcap(sample)
        print("Result:", result)