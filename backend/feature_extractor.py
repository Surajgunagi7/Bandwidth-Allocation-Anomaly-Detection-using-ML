#!/usr/bin/env python3
"""
Feature Extraction Module for PCAP Files
Extracts features for both bandwidth prediction and anomaly detection
"""

from scapy.all import rdpcap, IP, TCP, UDP, ICMP
from collections import defaultdict
import numpy as np
import pandas as pd
from datetime import datetime
import hashlib
import logging
from typing import Dict, List, Tuple
from scipy.stats import entropy
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FlowKey:
    """Represents a network flow (5-tuple)"""
    def __init__(self, src_mac, dst_mac, src_ip, dst_ip, protocol):
        self.src_mac = src_mac
        self.dst_mac = dst_mac
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.protocol = protocol
    
    def __hash__(self):
        return hash((self.src_mac, self.dst_mac, self.src_ip, self.dst_ip, self.protocol))
    
    def __eq__(self, other):
        return (self.src_mac == other.src_mac and 
                self.dst_mac == other.dst_mac and
                self.src_ip == other.src_ip and 
                self.dst_ip == other.dst_ip and
                self.protocol == other.protocol)


class FlowFeatures:
    """Stores features for a single flow"""
    def __init__(self):
        self.packet_sizes = []
        self.timestamps = []
        self.tcp_flags = []
        self.dst_ports = set()
        self.src_ports = set()
        self.protocols = set()
        self.total_bytes = 0
        self.total_packets = 0
        self.failed_connections = 0
        self.new_connections = 0


class PCAPFeatureExtractor:
    """Extract ML features from PCAP files"""
    
    # Ports commonly used for encrypted traffic
    ENCRYPTED_PORTS = {443, 8443, 993, 995, 22, 3389}
    
    def __init__(self, window_size: int = 60):
        """
        Args:
            window_size: Time window in seconds for flow aggregation
        """
        self.window_size = window_size
        self.flows = defaultdict(FlowFeatures)
        
    def extract_from_pcap(self, pcap_file: str) -> pd.DataFrame:
        """
        Extract features from PCAP file
        
        Args:
            pcap_file: Path to PCAP file
            
        Returns:
            DataFrame with extracted features per MAC address
        """
        logger.info(f"Loading PCAP file: {pcap_file}")
        
        try:
            packets = rdpcap(pcap_file)
            logger.info(f"Loaded {len(packets)} packets")
        except Exception as e:
            logger.error(f"Failed to read PCAP: {e}")
            return pd.DataFrame()
        
        if len(packets) == 0:
            logger.warning("Empty PCAP file")
            return pd.DataFrame()
        
        # Process packets and aggregate by flow
        self._process_packets(packets)
        
        # Convert flows to features
        features_df = self._compute_features()
        
        logger.info(f"Extracted features for {len(features_df)} MAC addresses")
        return features_df
    
    def _process_packets(self, packets):
        """Process packets and organize into flows"""
        self.flows.clear()
        
        for pkt in packets:
            # Skip non-IP packets
            if not pkt.haslayer(IP):
                continue
            
            # Extract metadata
            src_mac = pkt.src if hasattr(pkt, 'src') else 'unknown'
            dst_mac = pkt.dst if hasattr(pkt, 'dst') else 'unknown'
            src_ip = pkt[IP].src
            dst_ip = pkt[IP].dst
            protocol = pkt[IP].proto
            timestamp = float(pkt.time)
            packet_size = len(pkt)
            
            # Create flow key (aggregate by source MAC primarily)
            flow_key = self._create_flow_key(src_mac, dst_mac, src_ip, dst_ip, protocol)
            
            # Store packet features
            flow = self.flows[flow_key]
            flow.packet_sizes.append(packet_size)
            flow.timestamps.append(timestamp)
            flow.total_bytes += packet_size
            flow.total_packets += 1
            flow.protocols.add(protocol)
            
            # Protocol-specific features
            if pkt.haslayer(TCP):
                tcp_layer = pkt[TCP]
                flow.tcp_flags.append(tcp_layer.flags)
                flow.dst_ports.add(tcp_layer.dport)
                flow.src_ports.add(tcp_layer.sport)
                
                # Track connection attempts
                if tcp_layer.flags & 0x02:  # SYN flag
                    flow.new_connections += 1
                if tcp_layer.flags & 0x04:  # RST flag
                    flow.failed_connections += 1
            
            elif pkt.haslayer(UDP):
                udp_layer = pkt[UDP]
                flow.dst_ports.add(udp_layer.dport)
                flow.src_ports.add(udp_layer.sport)
    
    def _create_flow_key(self, src_mac, dst_mac, src_ip, dst_ip, protocol) -> str:
        """Create unique flow identifier (aggregate by source MAC)"""
        return f"{src_mac}_{protocol}"
    
    def _compute_features(self) -> pd.DataFrame:
        """Compute features from aggregated flows"""
        feature_list = []
        
        for flow_key, flow in self.flows.items():
            if flow.total_packets < 2:  # Skip flows with insufficient data
                continue
            
            # Extract MAC address from flow key
            mac_address = flow_key.split('_')[0]

            if mac_address in Config.KNOWN_AP_MACS:
                continue  # skip AP itself

            # Basic features
            features = {
                'mac_address': mac_address,
                'total_bytes': flow.total_bytes,
                'total_packets': flow.total_packets,
            }
            
            # Temporal features
            timestamps = np.array(flow.timestamps)
            flow_duration = timestamps.max() - timestamps.min()
            features['flow_duration'] = max(flow_duration, 0.001)  # Avoid division by zero
            
            features['bytes_per_second'] = flow.total_bytes / features['flow_duration']
            features['packets_per_second'] = flow.total_packets / features['flow_duration']
            
            # Packet size statistics
            packet_sizes = np.array(flow.packet_sizes)
            features['avg_packet_size'] = np.mean(packet_sizes)
            features['std_packet_size'] = np.std(packet_sizes)
            features['packet_size_variance'] = np.std(packet_sizes) / (np.mean(packet_sizes) + 1e-6)
            
            # Inter-arrival time
            if len(timestamps) > 1:
                inter_arrival_times = np.diff(timestamps) * 1000  # Convert to ms
                features['avg_inter_arrival_time'] = np.mean(inter_arrival_times)
            else:
                features['avg_inter_arrival_time'] = 0.0
            
            # Protocol features
            protocol_num = int(flow_key.split('_')[1])
            features['protocol_type'] = self._encode_protocol(protocol_num)
            features['protocol_diversity'] = len(flow.protocols)
            
            # Port features
            features['unique_dst_ports'] = len(flow.dst_ports)
            features['unique_src_ports'] = len(flow.src_ports)
            
            # Encryption indicator (based on common encrypted ports)
            features['is_encrypted'] = int(bool(flow.dst_ports & self.ENCRYPTED_PORTS))
            
            # TCP-specific features
            if flow.tcp_flags:
                syn_count = sum(1 for f in flow.tcp_flags if f & 0x02)
                ack_count = sum(1 for f in flow.tcp_flags if f & 0x10)
                fin_count = sum(1 for f in flow.tcp_flags if f & 0x01)
                total_flags = len(flow.tcp_flags)
                features['tcp_flag_ratio'] = (syn_count + ack_count + fin_count) / total_flags
            else:
                features['tcp_flag_ratio'] = 0.0
            
            # Entropy (measure of randomness in packet sizes)
            features['payload_entropy'] = self._calculate_entropy(packet_sizes)
            
            # Bidirectional ratio (simplified - would need proper flow matching)
            features['bidirectional_ratio'] = 0.5  # Placeholder (prev= 1.0)
            
            # Time of day
            if len(timestamps) > 0:
                features['time_of_day'] = datetime.fromtimestamp(timestamps[0]).hour
            else:
                features['time_of_day'] = 0
            
            # Anomaly-specific features
            features['connection_rate'] = flow.new_connections / features['flow_duration']
            features['failed_connection_ratio'] = (
                flow.failed_connections / max(flow.new_connections, 1)
            )
            features['port_scan_indicator'] = len(flow.dst_ports) / features['flow_duration']
            
            feature_list.append(features)
        
        # Create DataFrame
        df = pd.DataFrame(feature_list)
        
        # Aggregate by MAC address (sum/average features for same MAC)
        if len(df) > 0:
            df = self._aggregate_by_mac(df)
        
        return df
    
    def _aggregate_by_mac(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate features by MAC address"""
        agg_dict = {
            'total_bytes': 'sum',
            'total_packets': 'sum',
            'flow_duration': 'max',
            'bytes_per_second': 'mean',
            'packets_per_second': 'mean',
            'avg_packet_size': 'mean',
            'std_packet_size': 'mean',
            'packet_size_variance': 'mean',
            'avg_inter_arrival_time': 'mean',
            'protocol_type': 'first',
            'protocol_diversity': 'sum',
            'unique_dst_ports': 'sum',
            'unique_src_ports': 'sum',
            'is_encrypted': 'max',
            'tcp_flag_ratio': 'mean',
            'payload_entropy': 'mean',
            'bidirectional_ratio': 'mean',
            'time_of_day': 'first',
            'connection_rate': 'mean',
            'failed_connection_ratio': 'mean',
            'port_scan_indicator': 'mean',
        }
        
        aggregated = df.groupby('mac_address').agg(agg_dict).reset_index()
        return aggregated
    
    def _encode_protocol(self, protocol_num: int) -> int:
        """Encode protocol number to categorical value"""
        protocol_map = {
            6: 1,   # TCP
            17: 2,  # UDP
            1: 3,   # ICMP
        }
        return protocol_map.get(protocol_num, 0)
    
    def _calculate_entropy(self, values: np.ndarray) -> float:
        """Calculate Shannon entropy of packet sizes"""
        if len(values) == 0:
            return 0.0
        
        # Bin values into histogram
        hist, _ = np.histogram(values, bins=20)
        hist = hist[hist > 0]  # Remove zero bins
        
        # Calculate entropy
        probabilities = hist / hist.sum()
        return float(entropy(probabilities))
    
    def get_bandwidth_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract subset of features for bandwidth prediction model"""
        bandwidth_features = [
            'mac_address',
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
        return df[bandwidth_features].copy()
    
    def get_anomaly_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract all features for anomaly detection model"""
        # Anomaly model uses all features
        return df.copy()


def process_pcap_file(pcap_path: str, output_csv: str = None) -> Dict[str, pd.DataFrame]:
    """
    Main function to process PCAP and extract features
    
    Args:
        pcap_path: Path to PCAP file
        output_csv: Optional path to save features as CSV
        
    Returns:
        Dictionary with 'bandwidth' and 'anomaly' DataFrames
    """
    extractor = PCAPFeatureExtractor(window_size=60)
    
    # Extract all features
    all_features = extractor.extract_from_pcap(pcap_path)
    
    if all_features.empty:
        logger.warning("No features extracted from PCAP")
        return {'bandwidth': pd.DataFrame(), 'anomaly': pd.DataFrame()}
    
    # Get model-specific features
    bandwidth_df = extractor.get_bandwidth_features(all_features)
    anomaly_df = extractor.get_anomaly_features(all_features)
    
    # Save to CSV if requested
    if output_csv:
        all_features.to_csv(output_csv, index=False)
        logger.info(f"Features saved to {output_csv}")
    
    logger.info(f"Bandwidth features shape: {bandwidth_df.shape}")
    logger.info(f"Anomaly features shape: {anomaly_df.shape}")
    
    return {
        'bandwidth': bandwidth_df,
        'anomaly': anomaly_df,
        'all': all_features
    }


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python feature_extractor.py <pcap_file> [output_csv]")
        sys.exit(1)
    
    pcap_file = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "extracted_features.csv"
    
    # Process PCAP
    features = process_pcap_file(pcap_file, output_csv)
    
    # Display summary
    print("\n=== Feature Extraction Summary ===")
    print(f"Total MACs processed: {len(features['all'])}")
    print("\nBandwidth Features (first 3 rows):")
    print(features['bandwidth'].head(3))
    print("\nAnomaly Features (first 3 rows):")
    print(features['anomaly'].head(3))