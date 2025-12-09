"""
Complete Backend System for Bandwidth Allocation & Anomaly Detection
Handles traffic collection, buffering, ML inference, and enforcement
"""

from flask import Flask, request, jsonify
from scapy.all import rdpcap, IP, TCP, UDP, ICMP
import numpy as np
import pandas as pd
from collections import defaultdict, deque
from datetime import datetime
import threading
import time
import os
import pickle
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
import subprocess
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
WINDOW_LENGTH = 3  # seconds
BUFFER_SIZE = 10  # windows per MAC (30s total)
DECISION_INTERVAL = 7  # seconds
TRAFFIC_CHANGE_THRESHOLD = 0.25  # 25% change triggers immediate decision
PCAP_DIR = "pcaps"
MODEL_DIR = "models"
AP_MAC = "02:00:00:00:00:00"  # Your AP MAC - CONFIGURE THIS
TOTAL_BANDWIDTH = 100  # Mbps - CONFIGURE THIS

# ==================== GLOBAL STATE ====================
# Buffer: {mac_address: deque([window_features_dict, ...])}
traffic_buffer = defaultdict(lambda: deque(maxlen=BUFFER_SIZE))
last_enforcement_time = time.time()
last_total_bytes = 0
ml_models = {}
scaler = None

# Thread lock for concurrent access
buffer_lock = threading.Lock()

# Ensure directories exist
os.makedirs(PCAP_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)


# ==================== FEATURE EXTRACTION ====================
def extract_features_from_pcap(pcap_path):
    """
    Extract comprehensive features from PCAP file
    Returns: dict with per-MAC features
    """
    try:
        packets = rdpcap(pcap_path)
        mac_stats = defaultdict(lambda: {
            'packet_count': 0,
            'total_bytes': 0,
            'tcp_count': 0,
            'udp_count': 0,
            'icmp_count': 0,
            'other_count': 0,
            'avg_packet_size': 0,
            'unique_dst_ips': set(),
            'unique_src_ips': set(),
            'unique_dst_ports': set(),
            'unique_src_ports': set(),
            'tcp_syn_count': 0,
            'tcp_fin_count': 0,
            'tcp_rst_count': 0,
            'ip_count': 0,
            'payload_bytes': 0,
            'inter_arrival_times': [],
            'packet_sizes': []
        })
        
        last_time = {}
        
        for pkt in packets:
            # Skip non-Ethernet packets
            if not hasattr(pkt, 'src'):
                continue
                
            src_mac = pkt.src
            dst_mac = pkt.dst
            
            # Skip AP MAC
            if src_mac == AP_MAC or dst_mac == AP_MAC:
                continue
            
            # Use source MAC as primary identifier
            mac = src_mac
            stats = mac_stats[mac]
            
            # Basic counts
            stats['packet_count'] += 1
            stats['total_bytes'] += len(pkt)
            stats['packet_sizes'].append(len(pkt))
            
            # Inter-arrival time
            pkt_time = float(pkt.time)
            if mac in last_time:
                iat = pkt_time - last_time[mac]
                stats['inter_arrival_times'].append(iat)
            last_time[mac] = pkt_time
            
            # Protocol analysis
            if IP in pkt:
                stats['ip_count'] += 1
                stats['unique_src_ips'].add(pkt[IP].src)
                stats['unique_dst_ips'].add(pkt[IP].dst)
                
                if TCP in pkt:
                    stats['tcp_count'] += 1
                    stats['unique_src_ports'].add(pkt[TCP].sport)
                    stats['unique_dst_ports'].add(pkt[TCP].dport)
                    
                    # TCP flags
                    flags = pkt[TCP].flags
                    if flags & 0x02:  # SYN
                        stats['tcp_syn_count'] += 1
                    if flags & 0x01:  # FIN
                        stats['tcp_fin_count'] += 1
                    if flags & 0x04:  # RST
                        stats['tcp_rst_count'] += 1
                    
                    if hasattr(pkt[TCP], 'payload'):
                        stats['payload_bytes'] += len(pkt[TCP].payload)
                        
                elif UDP in pkt:
                    stats['udp_count'] += 1
                    stats['unique_src_ports'].add(pkt[UDP].sport)
                    stats['unique_dst_ports'].add(pkt[UDP].dport)
                    
                    if hasattr(pkt[UDP], 'payload'):
                        stats['payload_bytes'] += len(pkt[UDP].payload)
                        
                elif ICMP in pkt:
                    stats['icmp_count'] += 1
                else:
                    stats['other_count'] += 1
            else:
                stats['other_count'] += 1
        
        # Compute derived features
        features_per_mac = {}
        for mac, stats in mac_stats.items():
            if stats['packet_count'] == 0:
                continue
                
            features = {
                'mac': mac,
                'timestamp': datetime.now().isoformat(),
                
                # Volume features
                'packet_count': stats['packet_count'],
                'total_bytes': stats['total_bytes'],
                'avg_packet_size': stats['total_bytes'] / stats['packet_count'],
                'bytes_per_second': stats['total_bytes'] / WINDOW_LENGTH,
                'packets_per_second': stats['packet_count'] / WINDOW_LENGTH,
                
                # Protocol distribution
                'tcp_ratio': stats['tcp_count'] / stats['packet_count'],
                'udp_ratio': stats['udp_count'] / stats['packet_count'],
                'icmp_ratio': stats['icmp_count'] / stats['packet_count'],
                'other_ratio': stats['other_count'] / stats['packet_count'],
                
                # Connection features
                'unique_dst_ips': len(stats['unique_dst_ips']),
                'unique_src_ips': len(stats['unique_src_ips']),
                'unique_dst_ports': len(stats['unique_dst_ports']),
                'unique_src_ports': len(stats['unique_src_ports']),
                
                # TCP behavior
                'tcp_syn_ratio': stats['tcp_syn_count'] / max(stats['tcp_count'], 1),
                'tcp_fin_ratio': stats['tcp_fin_count'] / max(stats['tcp_count'], 1),
                'tcp_rst_ratio': stats['tcp_rst_count'] / max(stats['tcp_count'], 1),
                
                # Payload
                'payload_ratio': stats['payload_bytes'] / stats['total_bytes'] if stats['total_bytes'] > 0 else 0,
                
                # Timing features
                'avg_iat': np.mean(stats['inter_arrival_times']) if stats['inter_arrival_times'] else 0,
                'std_iat': np.std(stats['inter_arrival_times']) if len(stats['inter_arrival_times']) > 1 else 0,
                'std_packet_size': np.std(stats['packet_sizes']) if len(stats['packet_sizes']) > 1 else 0,
            }
            
            features_per_mac[mac] = features
        
        return features_per_mac
        
    except Exception as e:
        logger.error(f"Error extracting features from {pcap_path}: {e}")
        return {}


def get_ml_features(feature_dict):
    """
    Convert feature dict to numpy array for ML models
    Order must match training data
    """
    feature_order = [
        'packet_count', 'total_bytes', 'avg_packet_size', 'bytes_per_second',
        'packets_per_second', 'tcp_ratio', 'udp_ratio', 'icmp_ratio',
        'other_ratio', 'unique_dst_ips', 'unique_src_ips', 'unique_dst_ports',
        'unique_src_ports', 'tcp_syn_ratio', 'tcp_fin_ratio', 'tcp_rst_ratio',
        'payload_ratio', 'avg_iat', 'std_iat', 'std_packet_size'
    ]
    
    return np.array([feature_dict.get(f, 0) for f in feature_order]).reshape(1, -1)


# ==================== ML MODELS ====================
def load_models():
    """Load or initialize ML models"""
    global ml_models, scaler
    
    rf_path = os.path.join(MODEL_DIR, 'rf_model.pkl')
    if_path = os.path.join(MODEL_DIR, 'if_model.pkl')
    scaler_path = os.path.join(MODEL_DIR, 'scaler.pkl')
    
    if os.path.exists(rf_path) and os.path.exists(if_path) and os.path.exists(scaler_path):
        with open(rf_path, 'rb') as f:
            ml_models['rf'] = pickle.load(f)
        with open(if_path, 'rb') as f:
            ml_models['if'] = pickle.load(f)
        with open(scaler_path, 'rb') as f:
            scaler = pickle.load(f)
        logger.info("Loaded existing models")
    else:
        # Initialize with default models
        ml_models['rf'] = RandomForestClassifier(n_estimators=100, random_state=42)
        ml_models['if'] = IsolationForest(contamination=0.1, random_state=42)
        scaler = StandardScaler()
        logger.warning("Initialized default models - train with real data!")


def predict_priority(features):
    """
    Predict traffic priority class using Random Forest
    Returns: 0 (low), 1 (medium), 2 (high)
    """
    try:
        X = get_ml_features(features)
        X_scaled = scaler.transform(X)
        priority = ml_models['rf'].predict(X_scaled)[0]
        return int(priority)
    except Exception as e:
        logger.error(f"RF prediction error: {e}")
        return 1  # Default to medium


def detect_anomaly(features):
    """
    Detect anomaly using Isolation Forest
    Returns: True if anomaly, False otherwise
    """
    try:
        X = get_ml_features(features)
        X_scaled = scaler.transform(X)
        prediction = ml_models['if'].predict(X_scaled)[0]
        return prediction == -1  # -1 means anomaly
    except Exception as e:
        logger.error(f"IF prediction error: {e}")
        return False


# ==================== DECISION & ENFORCEMENT ====================
def allocate_bandwidth():
    """
    Allocate bandwidth based on priorities and available BW
    Returns: dict {mac: bandwidth_mbps}
    """
    with buffer_lock:
        if not traffic_buffer:
            return {}
        
        # Get latest features for each MAC
        mac_priorities = {}
        for mac, windows in traffic_buffer.items():
            if windows:
                latest = windows[-1]
                priority = predict_priority(latest)
                mac_priorities[mac] = priority
        
        # Priority weights
        priority_weights = {0: 1, 1: 2, 2: 4}
        
        # Calculate allocation
        total_weight = sum(priority_weights[p] for p in mac_priorities.values())
        allocations = {}
        
        for mac, priority in mac_priorities.items():
            weight = priority_weights[priority]
            bw = (weight / total_weight) * TOTAL_BANDWIDTH
            allocations[mac] = round(bw, 2)
        
        return allocations


def enforce_bandwidth(mac, bandwidth_mbps):
    """
    Enforce bandwidth limit using TC commands
    This assumes stations are connected via interfaces like sta1-wlan0
    """
    try:
        # Convert MAC to interface name (you may need to adjust this)
        # This is a placeholder - adjust based on your topology
        interface = f"sta{mac.replace(':', '')[-2:]}-wlan0"
        
        # Clear existing rules
        subprocess.run(
            f"tc qdisc del dev {interface} root 2>/dev/null",
            shell=True,
            check=False
        )
        
        # Add HTB qdisc with rate limit
        rate = f"{bandwidth_mbps}mbit"
        subprocess.run(
            f"tc qdisc add dev {interface} root handle 1: htb default 10",
            shell=True,
            check=True
        )
        subprocess.run(
            f"tc class add dev {interface} parent 1: classid 1:10 htb rate {rate}",
            shell=True,
            check=True
        )
        
        logger.info(f"Enforced {bandwidth_mbps} Mbps on {mac} ({interface})")
        return True
        
    except Exception as e:
        logger.error(f"Enforcement error for {mac}: {e}")
        return False


def run_decision():
    """
    Main decision logic - runs periodically or on events
    """
    logger.info("Running decision cycle...")
    
    # 1. Check for anomalies
    anomalies = []
    with buffer_lock:
        for mac, windows in traffic_buffer.items():
            if windows:
                latest = windows[-1]
                if detect_anomaly(latest):
                    anomalies.append({
                        'mac': mac,
                        'timestamp': latest['timestamp'],
                        'bytes': latest['total_bytes']
                    })
    
    if anomalies:
        logger.warning(f"Detected {len(anomalies)} anomalies: {anomalies}")
    
    # 2. Allocate bandwidth
    allocations = allocate_bandwidth()
    
    # 3. Enforce
    for mac, bw in allocations.items():
        enforce_bandwidth(mac, bw)
    
    logger.info(f"Bandwidth allocations: {allocations}")
    
    return {
        'allocations': allocations,
        'anomalies': anomalies,
        'timestamp': datetime.now().isoformat()
    }


# ==================== BACKGROUND DECISION THREAD ====================
def decision_loop():
    """Background thread for periodic decisions"""
    while True:
        time.sleep(DECISION_INTERVAL)
        run_decision()


# ==================== API ENDPOINTS ====================
@app.route('/traffic', methods=['POST'])
def receive_traffic():
    """
    Receive PCAP file from collector
    """
    global last_total_bytes, last_enforcement_time
    
    try:
        # Save PCAP
        pcap_file = request.files.get('pcap')
        if not pcap_file:
            return jsonify({'error': 'No PCAP file'}), 400
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pcap_path = os.path.join(PCAP_DIR, f'traffic_{timestamp}.pcap')
        pcap_file.save(pcap_path)
        
        # Extract features
        features_per_mac = extract_features_from_pcap(pcap_path)
        
        # Update buffer
        with buffer_lock:
            for mac, features in features_per_mac.items():
                traffic_buffer[mac].append(features)
        
        # Check for new MAC or significant traffic change
        current_total = sum(f['total_bytes'] for f in features_per_mac.values())
        traffic_changed = False
        
        if last_total_bytes > 0:
            change_ratio = abs(current_total - last_total_bytes) / last_total_bytes
            if change_ratio > TRAFFIC_CHANGE_THRESHOLD:
                traffic_changed = True
                logger.info(f"Significant traffic change detected: {change_ratio:.2%}")
        
        last_total_bytes = current_total
        
        # Event-driven decision
        new_macs = [mac for mac in features_per_mac.keys() 
                    if len(traffic_buffer[mac]) == 1]
        
        if new_macs or traffic_changed:
            logger.info(f"Triggering event-driven decision (new MACs: {new_macs})")
            run_decision()
        
        # Cleanup old PCAP
        try:
            os.remove(pcap_path)
        except:
            pass
        
        return jsonify({
            'status': 'success',
            'macs_processed': list(features_per_mac.keys()),
            'timestamp': timestamp
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing traffic: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/status', methods=['GET'])
def get_status():
    """Get current system status"""
    with buffer_lock:
        status = {
            'active_macs': list(traffic_buffer.keys()),
            'buffer_sizes': {mac: len(windows) for mac, windows in traffic_buffer.items()},
            'total_bandwidth': TOTAL_BANDWIDTH,
            'models_loaded': 'rf' in ml_models and 'if' in ml_models
        }
    return jsonify(status)


@app.route('/allocations', methods=['GET'])
def get_allocations():
    """Get current bandwidth allocations"""
    allocations = allocate_bandwidth()
    return jsonify(allocations)


@app.route('/train', methods=['POST'])
def train_models():
    """
    Train models with uploaded dataset
    Expects CSV with features and labels
    """
    try:
        data_file = request.files.get('data')
        if not data_file:
            return jsonify({'error': 'No data file'}), 400
        
        # Read CSV
        df = pd.read_csv(data_file)
        
        # Separate features and labels
        feature_cols = [c for c in df.columns if c not in ['label', 'priority', 'mac', 'timestamp']]
        X = df[feature_cols].values
        
        # Train scaler
        scaler.fit(X)
        X_scaled = scaler.transform(X)
        
        # Train RF if priority column exists
        if 'priority' in df.columns:
            y_priority = df['priority'].values
            ml_models['rf'].fit(X_scaled, y_priority)
            logger.info(f"Trained RF with {len(X)} samples")
        
        # Train IF (unsupervised)
        ml_models['if'].fit(X_scaled)
        logger.info(f"Trained IF with {len(X)} samples")
        
        # Save models
        with open(os.path.join(MODEL_DIR, 'rf_model.pkl'), 'wb') as f:
            pickle.dump(ml_models['rf'], f)
        with open(os.path.join(MODEL_DIR, 'if_model.pkl'), 'wb') as f:
            pickle.dump(ml_models['if'], f)
        with open(os.path.join(MODEL_DIR, 'scaler.pkl'), 'wb') as f:
            pickle.dump(scaler, f)
        
        return jsonify({'status': 'Models trained and saved'}), 200
        
    except Exception as e:
        logger.error(f"Training error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== MAIN ====================
if __name__ == '__main__':
    logger.info("Starting Bandwidth Allocation & Anomaly Detection Backend")
    
    # Load models
    load_models()
    
    # Start decision thread
    decision_thread = threading.Thread(target=decision_loop, daemon=True)
    decision_thread.start()
    
    # Start Flask
    app.run(host='0.0.0.0', port=5000, debug=False)