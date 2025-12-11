#!/usr/bin/env python3
"""
ML Integration Module - FINAL FIXED VERSION
Eliminates sklearn feature name warnings by preserving DataFrames
"""

import os
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
import logging
from typing import Dict, List, Tuple
from datetime import datetime, UTC
from flask import request, jsonify
import json  
from config import Config
import warnings

from feature_extractor import process_pcap_file
from bandwidth_enforcer import BandwidthDecisionEngine, BandwidthAllocation

# Suppress warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MLModelManager:
    """Manages ML models for bandwidth prediction and anomaly detection"""
    
    # CRITICAL: Match training script feature order
    BANDWIDTH_FEATURES = [
        'avg_packet_size',
        'total_bytes',
        'total_packets',
        'flow_duration',
        'bytes_per_second',
        'packets_per_second',
        'protocol_type',
        'avg_inter_arrival_time',
        'std_packet_size',
        'unique_dst_ports',
        'tcp_flag_ratio',
        'payload_entropy',
        'bidirectional_ratio',
        'is_encrypted',
        'time_of_day'
    ]
    
    ANOMALY_FEATURES = [
        'avg_packet_size',
        'total_bytes',
        'total_packets',
        'flow_duration',
        'bytes_per_second',
        'packets_per_second',
        'protocol_type',
        'avg_inter_arrival_time',
        'std_packet_size',
        'unique_dst_ports',
        'tcp_flag_ratio',
        'payload_entropy',
        'bidirectional_ratio',
        'is_encrypted',
        'time_of_day',
        'connection_rate',
        'failed_connection_ratio',
        'port_scan_indicator',
        'packet_size_variance',
        'protocol_diversity'
    ]
    
    def __init__(self, models_dir: str = "./models"):
        """
        Args:
            models_dir: Directory containing trained model files
        """
        self.models_dir = Path(models_dir)
        self.bandwidth_model = None
        self.anomaly_model = None
        self.bandwidth_scaler = None
        self.anomaly_scaler = None
        
        self._load_models()
    
    def _load_models(self):
        """Load trained models from disk"""
        try:
            bandwidth_model_path = self.models_dir / "bandwidth_predictor.pkl"
            anomaly_model_path = self.models_dir / "anomaly_detector.pkl"
            bandwidth_scaler_path = self.models_dir / "bandwidth_scaler.pkl"
            anomaly_scaler_path = self.models_dir / "anomaly_scaler.pkl"
            
            if bandwidth_model_path.exists():
                self.bandwidth_model = joblib.load(bandwidth_model_path)
                logger.info("✓ Loaded bandwidth prediction model")
            else:
                logger.warning(f"⚠ Bandwidth model not found at {bandwidth_model_path}")
            
            if anomaly_model_path.exists():
                self.anomaly_model = joblib.load(anomaly_model_path)
                logger.info("✓ Loaded anomaly detection model")
            else:
                logger.warning(f"⚠ Anomaly model not found at {anomaly_model_path}")
            
            if bandwidth_scaler_path.exists():
                self.bandwidth_scaler = joblib.load(bandwidth_scaler_path)
                logger.info("✓ Loaded bandwidth feature scaler")
            else:
                logger.warning(f"⚠ Bandwidth scaler not found (using unscaled features)")
            
            if anomaly_scaler_path.exists():
                self.anomaly_scaler = joblib.load(anomaly_scaler_path)
                logger.info("✓ Loaded anomaly feature scaler")
            else:
                logger.warning(f"⚠ Anomaly scaler not found (using unscaled features)")
            
        except Exception as e:
            logger.error(f"❌ Failed to load models: {e}")
    
    def predict_bandwidth(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict bandwidth requirements for each MAC address
        FIXED: Preserves DataFrame structure to avoid sklearn warnings
        """
        if self.bandwidth_model is None:
            logger.error("❌ Bandwidth model not loaded - using defaults")
            result_df = features_df[['mac_address']].copy()
            result_df['predicted_bandwidth_kbps'] = 1000  # Default 1 Mbps
            return result_df
        
        try:
            # Extract features in EXACT order (excluding mac_address)
            X = features_df[self.BANDWIDTH_FEATURES].copy()
            
            logger.debug(f"Bandwidth prediction input shape: {X.shape}")
            
            # Separate numeric and categorical features for scaling
            numeric_features = [f for f in self.BANDWIDTH_FEATURES if f != 'protocol_type']
            
            # Scale only numeric features if scaler available
            if self.bandwidth_scaler is not None:
                try:
                    # Create a copy for scaling
                    X_scaled = X.copy()
                    
                    # Scale numeric features IN PLACE (preserves DataFrame)
                    X_scaled[numeric_features] = self.bandwidth_scaler.transform(X[numeric_features])
                    
                    # protocol_type remains unscaled (already in X_scaled)
                    
                except Exception as e:
                    logger.warning(f"⚠ Scaling failed, using unscaled features: {e}")
                    X_scaled = X
            else:
                X_scaled = X
            
            # CRITICAL: Pass DataFrame (not numpy array) to preserve feature names
            predictions = self.bandwidth_model.predict(X_scaled)
            
            # Create result DataFrame
            result_df = features_df[['mac_address']].copy()
            result_df['predicted_bandwidth_kbps'] = predictions
            
            # Ensure positive values and reasonable bounds
            result_df['predicted_bandwidth_kbps'] = result_df['predicted_bandwidth_kbps'].clip(
                lower=100,   # Min 100 kbps
                upper=100000 # Max 100 Mbps
            ).round().astype(int)
            
            logger.info(f"✓ Predicted bandwidth for {len(result_df)} devices")
            return result_df
            
        except Exception as e:
            logger.error(f"❌ Bandwidth prediction failed: {e}")
            logger.exception("Full traceback:")
            # Return defaults on error
            result_df = features_df[['mac_address']].copy()
            result_df['predicted_bandwidth_kbps'] = 1000
            return result_df
    
    def detect_anomalies(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect anomalies in traffic patterns
        FIXED: Preserves DataFrame structure to avoid sklearn warnings
        """
        if self.anomaly_model is None:
            logger.error("❌ Anomaly model not loaded - marking all as normal")
            result_df = features_df[['mac_address']].copy()
            result_df['is_anomaly'] = False
            result_df['anomaly_score'] = 0.0
            return result_df
        
        try:
            # Extract features in EXACT order (excluding mac_address)
            X = features_df[self.ANOMALY_FEATURES].copy()
            
            logger.debug(f"Anomaly detection input shape: {X.shape}")
            
            # Separate numeric and categorical features
            numeric_features = [f for f in self.ANOMALY_FEATURES if f != 'protocol_type']
            
            # Scale only numeric features if scaler available
            if self.anomaly_scaler is not None:
                try:
                    # Create a copy for scaling
                    X_scaled = X.copy()
                    
                    # Scale numeric features IN PLACE (preserves DataFrame)
                    X_scaled[numeric_features] = self.anomaly_scaler.transform(X[numeric_features])
                    
                    # protocol_type remains unscaled
                    
                except Exception as e:
                    logger.warning(f"⚠ Scaling failed, using unscaled features: {e}")
                    X_scaled = X
            else:
                X_scaled = X
            
            # CRITICAL: Pass DataFrame (not numpy array) to preserve feature names
            predictions = self.anomaly_model.predict(X_scaled)
            anomaly_scores = self.anomaly_model.score_samples(X_scaled)

            # hardcode for testing
            # -------- FORCE NO ANOMALIES -------------
            # result_df = features_df[['mac_address']].copy()
            # result_df['is_anomaly'] = False
            # result_df['anomaly_score'] = 0.0
            # logger.warning("⚠ Forced anomaly detector OFF — always normal")
            # return result_df
            # -----------------------------------------

            
            # Normalize scores to 0-1 range (lower score = more anomalous)
            # Convert negative scores to positive anomaly scores
            normalized_scores = 1 / (1 + np.exp(anomaly_scores))  # Sigmoid transformation
            
            # # Create result DataFrame
            result_df = features_df[['mac_address']].copy()
            result_df['is_anomaly'] = (predictions == -1)
            result_df['anomaly_score'] = normalized_scores
            
            anomaly_count = result_df['is_anomaly'].sum()
            logger.info(f"✓ Detected {anomaly_count} anomalies out of {len(result_df)} devices")
            
            return result_df
            
        except Exception as e:
            logger.error(f"❌ Anomaly detection failed: {e}")
            logger.exception("Full traceback:")
            # Return defaults on error
            result_df = features_df[['mac_address']].copy()
            result_df['is_anomaly'] = False
            result_df['anomaly_score'] = 0.0
            return result_df
    
    def classify_traffic(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Classify traffic type (video, web, bulk, etc.)
        Simplified heuristic-based classification
        """
        result_df = features_df[['mac_address']].copy()
        
        def classify_row(row):
            try:
                # VoIP/Video conferencing: consistent low-medium bandwidth, UDP
                if (row.get('protocol_type', 0) == 2 and  # UDP
                    row.get('bytes_per_second', 0) < 5000 and
                    row.get('std_packet_size', 0) < 200):
                    return 'voip'
                
                # Video streaming: medium-high bandwidth, consistent packets
                elif (row.get('bytes_per_second', 0) > 3000 and
                      row.get('bytes_per_second', 0) < 15000):
                    return 'video'
                
                # Bulk transfer: high bandwidth, TCP
                elif (row.get('protocol_type', 0) == 1 and  # TCP
                      row.get('bytes_per_second', 0) > 10000):
                    return 'bulk'
                
                # Web browsing: low-medium bandwidth, multiple ports
                elif row.get('unique_dst_ports', 0) > 3:
                    return 'web'
                
                else:
                    return 'unknown'
            except Exception as e:
                logger.warning(f"Classification failed for row: {e}")
                return 'unknown'
        
        result_df['traffic_class'] = features_df.apply(classify_row, axis=1)
        
        return result_df


class PipelineController:
    """
    Main controller that orchestrates the entire ML pipeline
    """
    
    def __init__(self,
                 models_dir: str = str(Config.MODELS_DIR),
                 interface: str = None,
                 update_interval: int = 10):
        
        # Use config value if not provided
        if interface is None:
            interface = os.getenv("AP_INTERFACE", Config.AP_INTERFACE)
        
        self.model_manager = MLModelManager(models_dir)
        self.decision_engine = BandwidthDecisionEngine(
            interface=interface,
            update_interval=update_interval,
            change_threshold=0.15
        )
        self.history = []  # Store recent predictions for trend analysis
        
    def process_pcap(self, pcap_path: str) -> Dict:
        """
        Process uploaded PCAP file through complete pipeline
        FIXED: Better error handling and logging
        """
        logger.info(f"🔄 Processing PCAP: {pcap_path}")
        
        try:
            # Step 1: Extract features
            features = process_pcap_file(pcap_path, output_csv=None)
            
            if features['all'].empty:
                logger.warning("⚠ No features extracted from PCAP")
                return {'status': 'error', 'message': 'No features extracted - empty or invalid PCAP'}
            
            all_features = features['all']
            logger.info(f"✓ Extracted features for {len(all_features)} device(s)")
            
            # Step 2: Run ML predictions
            bandwidth_predictions = self.model_manager.predict_bandwidth(features['bandwidth'])
            anomaly_predictions = self.model_manager.detect_anomalies(features['anomaly'])
            traffic_classes = self.model_manager.classify_traffic(all_features)
            
            # Step 3: Merge predictions
            merged_predictions = self._merge_predictions(
                all_features,
                bandwidth_predictions,
                anomaly_predictions,
                traffic_classes
            )
            
            logger.info(f"✓ Merged predictions for {len(merged_predictions)} device(s)")
            
            # Step 4: Enforce bandwidth allocations
            enforcement_results = self._enforce_allocations(merged_predictions)
            
            # Step 5: Store in history
            self._update_history(merged_predictions)
            
            # Step 6: Prepare response
            response = {
                'status': 'success',
                'timestamp': datetime.now(UTC).isoformat(),
                'devices_processed': len(merged_predictions),
                'anomalies_detected': int(merged_predictions['is_anomaly'].sum()),
                'predictions': merged_predictions.to_dict('records'),
                'enforcement': enforcement_results
            }
            
            logger.info(f"✓ Pipeline complete: {len(merged_predictions)} devices processed")
            return response
            
        except Exception as e:
            logger.error(f"❌ Pipeline processing failed: {e}")
            logger.exception("Full traceback:")
            return {'status': 'error', 'message': str(e)}
    
    def _merge_predictions(self,
                          features: pd.DataFrame,
                          bandwidth: pd.DataFrame,
                          anomalies: pd.DataFrame,
                          traffic: pd.DataFrame) -> pd.DataFrame:
        """Merge all predictions into single DataFrame"""
        
        merged = features[['mac_address']].copy()
        
        # Merge bandwidth predictions
        if not bandwidth.empty:
            merged = merged.merge(bandwidth, on='mac_address', how='left')
        else:
            merged['predicted_bandwidth_kbps'] = 1000  # Default
        
        # Merge anomaly predictions
        if not anomalies.empty:
            merged = merged.merge(anomalies, on='mac_address', how='left')
        else:
            merged['is_anomaly'] = False
            merged['anomaly_score'] = 0.0
        
        # Merge traffic class
        if not traffic.empty:
            merged = merged.merge(traffic, on='mac_address', how='left')
        else:
            merged['traffic_class'] = 'unknown'
        
        # Fill NaN values
        merged['predicted_bandwidth_kbps'].fillna(1000, inplace=True)
        merged['is_anomaly'].fillna(False, inplace=True)
        merged['anomaly_score'].fillna(0.0, inplace=True)
        merged['traffic_class'].fillna('unknown', inplace=True)
        
        return merged
    
    def _enforce_allocations(self, predictions: pd.DataFrame) -> Dict:
        """Enforce bandwidth allocations via decision engine"""
        
        # Convert DataFrame to list of dicts for decision engine
        prediction_dicts = []
        
        for _, row in predictions.iterrows():
            pred_dict = {
                'mac_address': row['mac_address'],
                'predicted_bandwidth_kbps': int(row['predicted_bandwidth_kbps']),
                'traffic_class': row['traffic_class'],
                'is_anomaly': bool(row['is_anomaly']),
            }
            prediction_dicts.append(pred_dict)
        
        # Process through decision engine
        try:
            self.decision_engine.process_ml_predictions(prediction_dicts)
            
            logger.info(f"✓ Enforced bandwidth for {len(prediction_dicts)} device(s)")
            return {
                'status': 'enforced',
                'devices_updated': len(prediction_dicts),
                'active_allocations': len(self.decision_engine.tc_controller.active_allocations)
            }
        
        except Exception as e:
            logger.error(f"❌ Enforcement failed: {e}")
            logger.exception("Full traceback:")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _update_history(self, predictions: pd.DataFrame, max_history: int = 10):
        """Store predictions in rolling history"""
        self.history.append({
            'timestamp': datetime.now(UTC).isoformat(),
            'predictions': predictions.to_dict('records')
        })
        
        # Keep only recent history
        if len(self.history) > max_history:
            self.history = self.history[-max_history:]
    
    def get_statistics(self) -> Dict:
        """Get current statistics and status"""
        try:
            tc_stats = self.decision_engine.tc_controller.get_stats()
            
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
                'tc_stats': tc_stats,
                'history_entries': len(self.history)
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}


# Example usage
if __name__ == "__main__":
    # Initialize pipeline
    pipeline = PipelineController(
        models_dir="./models",
        interface="ap1-wlan1",
        update_interval=10
    )
    
    # Process a sample PCAP
    sample_pcap = "./test_data/sample_traffic.pcap"
    if os.path.exists(sample_pcap):
        result = pipeline.process_pcap(sample_pcap)
        print("Pipeline Result:")
        print(json.dumps(result, indent=2))
    else:
        print(f"Sample PCAP not found: {sample_pcap}")