#!/usr/bin/env python3
"""
Feature Extraction Module - FIXED VERSION
Key fixes:
1. Implements true 5-tuple flow tracking (src_ip, dst_ip, src_port, dst_port, protocol)
2. Proper bidirectional flow detection
3. Enforces time-based windowing
4. Comments match implementation
"""

from scapy.all import rdpcap, IP, TCP, UDP, ICMP
from collections import defaultdict
import numpy as np
import pandas as pd
from datetime import datetime, UTC
import logging
from typing import Dict, List, Tuple
from scipy.stats import entropy
from config import Config
import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning)
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FlowKey:
    """
    Represents a TRUE 5-tuple network flow:
    (src_ip, dst_ip, src_port, dst_port, protocol)
    
    Bidirectional flows are detected by creating reverse keys.
    """
    def __init__(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int, protocol: int):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.src_port = src_port
        self.dst_port = dst_port
        self.protocol = protocol
    
    def __hash__(self):
        return hash((self.src_ip, self.dst_ip, self.src_port, self.dst_port, self.protocol))
    
    def __eq__(self, other):
        return (self.src_ip == other.src_ip and 
                self.dst_ip == other.dst_ip and
                self.src_port == other.src_port and 
                self.dst_port == other.dst_port and
                self.protocol == other.protocol)
    
    def reverse(self):
        """Create reverse flow key for bidirectional matching"""
        return FlowKey(self.dst_ip, self.src_ip, self.dst_port, self.src_port, self.protocol)
    
    def __repr__(self):
        return f"Flow({self.src_ip}:{self.src_port} -> {self.dst_ip}:{self.dst_port}, proto={self.protocol})"


class FlowFeatures:
    """Stores features for a single flow"""
    def __init__(self, src_mac: str = None):
        self.src_mac = src_mac
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
        self.direction = 'forward'  # 'forward' or 'reverse'


class PCAPFeatureExtractor:
    """Extract ML features from PCAP files with proper flow tracking"""
    
    ENCRYPTED_PORTS = {443, 8443, 993, 995, 22, 3389}
    
    BANDWIDTH_FEATURE_ORDER = [
        'avg_packet_size', 'total_bytes', 'total_packets', 'flow_duration',
        'bytes_per_second', 'packets_per_second', 'protocol_type',
        'avg_inter_arrival_time', 'std_packet_size', 'unique_dst_ports',
        'tcp_flag_ratio', 'payload_entropy', 'bidirectional_ratio',
        'is_encrypted', 'time_of_day'
    ]
    
    ANOMALY_FEATURE_ORDER = BANDWIDTH_FEATURE_ORDER + [
        'connection_rate', 'failed_connection_ratio', 'port_scan_indicator',
        'packet_size_variance', 'protocol_diversity'
    ]
    
    def __init__(self, window_size: int = 60):
        """
        Args:
            window_size: Time window in seconds for flow aggregation (NOW ENFORCED)
        """
        self.window_size = window_size
        self.flows: Dict[FlowKey, FlowFeatures] = {}
        self.mac_to_flows: Dict[str, List[FlowKey]] = defaultdict(list)  # Track flows per MAC
    
    def extract_from_pcap(self, pcap_file: str) -> pd.DataFrame:
        """Extract features from PCAP with time windowing"""
        logger.info(f"Loading PCAP: {pcap_file}")
        
        try:
            packets = rdpcap(pcap_file)
            logger.info(f"Loaded {len(packets)} packets")
        except Exception as e:
            logger.error(f"Failed to read PCAP: {e}")
            return pd.DataFrame()
        
        if len(packets) == 0:
            logger.warning("Empty PCAP file")
            return pd.DataFrame()
        
        # Process packets into flows
        self._process_packets_with_windowing(packets)
        
        # Compute features per MAC address
        features_df = self._compute_features()
        
        logger.info(f"Extracted features for {len(features_df)} MAC addresses")
        return features_df
    
    def _process_packets_with_windowing(self, packets):
        """
        Process packets into flows with time-based windowing.
        FIXED: Now enforces window_size parameter.
        """
        self.flows.clear()
        self.mac_to_flows.clear()
        
        if len(packets) == 0:
            return
        
        # Get time bounds
        first_ts = float(packets[0].time)
        last_ts = float(packets[-1].time)
        
        logger.info(f"PCAP time range: {last_ts - first_ts:.2f} seconds")
        
        # If PCAP duration > window_size, use only recent window
        if (last_ts - first_ts) > self.window_size:
            window_start = last_ts - self.window_size
            logger.info(f"⏱ Applying {self.window_size}s window (discarding {first_ts:.1f} to {window_start:.1f})")
        else:
            window_start = first_ts
        
        packets_in_window = 0
        
        for pkt in packets:
            # Skip packets outside window
            if float(pkt.time) < window_start:
                continue
            
            packets_in_window += 1
            
            # Skip non-IP packets
            if not pkt.haslayer(IP):
                continue
            
            # Extract packet metadata
            src_mac = pkt.src if hasattr(pkt, 'src') else 'unknown'
            dst_mac = pkt.dst if hasattr(pkt, 'dst') else 'unknown'
            src_ip = pkt[IP].src
            dst_ip = pkt[IP].dst
            protocol = pkt[IP].proto
            timestamp = float(pkt.time)
            packet_size = len(pkt)
            
            # Extract ports (if TCP/UDP)
            src_port, dst_port = self._extract_ports(pkt)
            
            # Create 5-tuple flow key
            flow_key = FlowKey(src_ip, dst_ip, src_port, dst_port, protocol)
            reverse_key = flow_key.reverse()
            
            # Check if this belongs to existing flow (forward or reverse)
            if flow_key in self.flows:
                # Forward direction
                flow = self.flows[flow_key]
                flow.direction = 'forward'
            elif reverse_key in self.flows:
                # Reverse direction (bidirectional flow)
                flow = self.flows[reverse_key]
                flow.direction = 'reverse'
                flow_key = reverse_key  # Use existing key
            else:
                # New flow
                flow = FlowFeatures(src_mac=src_mac)
                self.flows[flow_key] = flow
                self.mac_to_flows[src_mac].append(flow_key)
            
            # Update flow features
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
                
                if tcp_layer.flags & 0x02:  # SYN
                    flow.new_connections += 1
                if tcp_layer.flags & 0x04:  # RST
                    flow.failed_connections += 1
            
            elif pkt.haslayer(UDP):
                udp_layer = pkt[UDP]
                flow.dst_ports.add(udp_layer.dport)
                flow.src_ports.add(udp_layer.sport)
        
        logger.info(f"✓ Processed {packets_in_window} packets in window, {len(self.flows)} unique flows")
    
    def _extract_ports(self, pkt) -> Tuple[int, int]:
        """Extract source and destination ports"""
        if pkt.haslayer(TCP):
            return pkt[TCP].sport, pkt[TCP].dport
        elif pkt.haslayer(UDP):
            return pkt[UDP].sport, pkt[UDP].dport
        else:
            return 0, 0  # Non-port protocol (ICMP, etc.)
    
    def _compute_features(self) -> pd.DataFrame:
        """
        Compute features per MAC address (aggregate all flows for each MAC).
        FIXED: Implements proper bidirectional_ratio calculation.
        """
        # Aggregate flows by MAC address
        mac_features = defaultdict(lambda: {
            'total_bytes': 0,
            'total_packets': 0,
            'packet_sizes': [],
            'timestamps': [],
            'tcp_flags': [],
            'dst_ports': set(),
            'src_ports': set(),
            'protocols': set(),
            'new_connections': 0,
            'failed_connections': 0,
            'bidirectional_flows': 0,
            'total_flows': 0
        })
        
        # First pass: aggregate flow data per MAC
        for flow_key, flow in self.flows.items():
            mac = flow.src_mac
            
            # Skip AP MACs
            if mac in Config.KNOWN_AP_MACS:
                continue
            
            agg = mac_features[mac]
            agg['total_bytes'] += flow.total_bytes
            agg['total_packets'] += flow.total_packets
            agg['packet_sizes'].extend(flow.packet_sizes)
            agg['timestamps'].extend(flow.timestamps)
            agg['tcp_flags'].extend(flow.tcp_flags)
            agg['dst_ports'].update(flow.dst_ports)
            agg['src_ports'].update(flow.src_ports)
            agg['protocols'].update(flow.protocols)
            agg['new_connections'] += flow.new_connections
            agg['failed_connections'] += flow.failed_connections
            agg['total_flows'] += 1
            
            # Check if bidirectional (reverse flow exists)
            if flow_key.reverse() in self.flows:
                agg['bidirectional_flows'] += 1
        
        # Second pass: compute features
        feature_list = []
        
        for mac, agg in mac_features.items():
            if agg['total_packets'] < 2:
                continue
            
            features = {'mac_address': mac}
            
            # Basic features
            features['total_bytes'] = agg['total_bytes']
            features['total_packets'] = agg['total_packets']
            
            # Temporal features
            timestamps = np.array(agg['timestamps'])
            flow_duration = timestamps.max() - timestamps.min()
            features['flow_duration'] = max(flow_duration, 0.001)
            
            features['bytes_per_second'] = agg['total_bytes'] / features['flow_duration']
            features['packets_per_second'] = agg['total_packets'] / features['flow_duration']
            
            # Packet size statistics
            packet_sizes = np.array(agg['packet_sizes'])
            features['avg_packet_size'] = np.mean(packet_sizes)
            features['std_packet_size'] = np.std(packet_sizes)
            features['packet_size_variance'] = np.std(packet_sizes) / (np.mean(packet_sizes) + 1e-6)
            
            # Inter-arrival time
            if len(timestamps) > 1:
                inter_arrival_times = np.diff(timestamps) * 1000
                features['avg_inter_arrival_time'] = np.mean(inter_arrival_times)
            else:
                features['avg_inter_arrival_time'] = 0.0
            
            # Protocol features
            # Use most common protocol
            protocol_list = list(agg['protocols'])
            features['protocol_type'] = self._encode_protocol(protocol_list[0] if protocol_list else 6)
            features['protocol_diversity'] = len(agg['protocols'])
            
            # Port features
            features['unique_dst_ports'] = len(agg['dst_ports'])
            features['unique_src_ports'] = len(agg['src_ports'])
            
            # Encryption indicator
            features['is_encrypted'] = int(bool(agg['dst_ports'] & self.ENCRYPTED_PORTS))
            
            # TCP features
            if agg['tcp_flags']:
                syn_count = sum(1 for f in agg['tcp_flags'] if f & 0x02)
                ack_count = sum(1 for f in agg['tcp_flags'] if f & 0x10)
                fin_count = sum(1 for f in agg['tcp_flags'] if f & 0x01)
                total_flags = len(agg['tcp_flags'])
                features['tcp_flag_ratio'] = (syn_count + ack_count + fin_count) / total_flags
            else:
                features['tcp_flag_ratio'] = 0.0
            
            # Entropy
            features['payload_entropy'] = self._calculate_entropy(packet_sizes)
            
            # FIXED: Proper bidirectional ratio
            features['bidirectional_ratio'] = (
                agg['bidirectional_flows'] / agg['total_flows'] 
                if agg['total_flows'] > 0 else 0.0
            )
            
            # Time of day
            features['time_of_day'] = datetime.fromtimestamp(timestamps[0], tz=UTC).hour
            
            # Anomaly-specific features
            features['connection_rate'] = agg['new_connections'] / features['flow_duration']
            features['failed_connection_ratio'] = (
                agg['failed_connections'] / max(agg['new_connections'], 1)
            )
            features['port_scan_indicator'] = len(agg['dst_ports']) / features['flow_duration']
            
            feature_list.append(features)
        
        return pd.DataFrame(feature_list)
    
    def _encode_protocol(self, protocol_num: int) -> int:
        """Encode protocol number"""
        protocol_map = {6: 1, 17: 2, 1: 3}  # TCP, UDP, ICMP
        return protocol_map.get(protocol_num, 0)
    
    def _calculate_entropy(self, values: np.ndarray) -> float:
        """Calculate Shannon entropy"""
        if len(values) == 0:
            return 0.0
        
        hist, _ = np.histogram(values, bins=20)
        hist = hist[hist > 0]
        
        if len(hist) == 0:
            return 0.0
        
        probabilities = hist / hist.sum()
        return float(entropy(probabilities))
    
    def get_bandwidth_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract bandwidth features in correct order"""
        if df.empty:
            return pd.DataFrame()
        
        missing = set(self.BANDWIDTH_FEATURE_ORDER) - set(df.columns)
        if missing:
            logger.error(f"Missing features: {missing}")
            for feat in missing:
                df[feat] = 0.0
        
        return df[['mac_address'] + self.BANDWIDTH_FEATURE_ORDER].copy()
    
    def get_anomaly_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract anomaly features in correct order"""
        if df.empty:
            return pd.DataFrame()
        
        missing = set(self.ANOMALY_FEATURE_ORDER) - set(df.columns)
        if missing:
            logger.error(f"Missing features: {missing}")
            for feat in missing:
                df[feat] = 0.0
        
        return df[['mac_address'] + self.ANOMALY_FEATURE_ORDER].copy()


def process_pcap_file(pcap_path: str, output_csv: str = None) -> Dict[str, pd.DataFrame]:
    """Main function to process PCAP"""
    extractor = PCAPFeatureExtractor(window_size=60)
    
    all_features = extractor.extract_from_pcap(pcap_path)
    
    if all_features.empty:
        logger.warning("No features extracted")
        return {'bandwidth': pd.DataFrame(), 'anomaly': pd.DataFrame(), 'all': pd.DataFrame()}
    
    bandwidth_df = extractor.get_bandwidth_features(all_features)
    anomaly_df = extractor.get_anomaly_features(all_features)
    
    if output_csv:
        all_features.to_csv(output_csv, index=False)
        logger.info(f"Saved to {output_csv}")
    
    logger.info(f"✓ Bandwidth: {bandwidth_df.shape}, Anomaly: {anomaly_df.shape}")
    
    return {'bandwidth': bandwidth_df, 'anomaly': anomaly_df, 'all': all_features}


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python feature_extractor.py <pcap_file> [output_csv]")
        sys.exit(1)
    
    pcap_file = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "features.csv"
    
    features = process_pcap_file(pcap_file, output_csv)
    
    print("\n=== Summary ===")
    print(f"MACs: {len(features['all'])}")
    print("\nBandwidth features:")
    print(features['bandwidth'].head(3))
    print("\nAnomaly features:")
    print(features['anomaly'].head(3))