"""
Dataset Preparation and Model Training Script
Processes PCAP files and trains ML models
"""

import os
import pandas as pd
import numpy as np
from scapy.all import rdpcap, IP, TCP, UDP, ICMP
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import pickle
import argparse
from collections import defaultdict

# Same feature extraction as backend
def extract_features_from_pcap(pcap_path, window_length=3, ap_mac="02:00:00:00:00:00"):
    """Extract features from PCAP file"""
    try:
        packets = rdpcap(pcap_path)
        mac_stats = defaultdict(lambda: {
            'packet_count': 0,
            'total_bytes': 0,
            'tcp_count': 0,
            'udp_count': 0,
            'icmp_count': 0,
            'other_count': 0,
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
            if not hasattr(pkt, 'src'):
                continue
                
            src_mac = pkt.src
            dst_mac = pkt.dst
            
            if src_mac == ap_mac or dst_mac == ap_mac:
                continue
            
            mac = src_mac
            stats = mac_stats[mac]
            
            stats['packet_count'] += 1
            stats['total_bytes'] += len(pkt)
            stats['packet_sizes'].append(len(pkt))
            
            pkt_time = float(pkt.time)
            if mac in last_time:
                iat = pkt_time - last_time[mac]
                stats['inter_arrival_times'].append(iat)
            last_time[mac] = pkt_time
            
            if IP in pkt:
                stats['ip_count'] += 1
                stats['unique_src_ips'].add(pkt[IP].src)
                stats['unique_dst_ips'].add(pkt[IP].dst)
                
                if TCP in pkt:
                    stats['tcp_count'] += 1
                    stats['unique_src_ports'].add(pkt[TCP].sport)
                    stats['unique_dst_ports'].add(pkt[TCP].dport)
                    
                    flags = pkt[TCP].flags
                    if flags & 0x02:
                        stats['tcp_syn_count'] += 1
                    if flags & 0x01:
                        stats['tcp_fin_count'] += 1
                    if flags & 0x04:
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
        
        features_list = []
        for mac, stats in mac_stats.items():
            if stats['packet_count'] == 0:
                continue
                
            features = {
                'mac': mac,
                'packet_count': stats['packet_count'],
                'total_bytes': stats['total_bytes'],
                'avg_packet_size': stats['total_bytes'] / stats['packet_count'],
                'bytes_per_second': stats['total_bytes'] / window_length,
                'packets_per_second': stats['packet_count'] / window_length,
                'tcp_ratio': stats['tcp_count'] / stats['packet_count'],
                'udp_ratio': stats['udp_count'] / stats['packet_count'],
                'icmp_ratio': stats['icmp_count'] / stats['packet_count'],
                'other_ratio': stats['other_count'] / stats['packet_count'],
                'unique_dst_ips': len(stats['unique_dst_ips']),
                'unique_src_ips': len(stats['unique_src_ips']),
                'unique_dst_ports': len(stats['unique_dst_ports']),
                'unique_src_ports': len(stats['unique_src_ports']),
                'tcp_syn_ratio': stats['tcp_syn_count'] / max(stats['tcp_count'], 1),
                'tcp_fin_ratio': stats['tcp_fin_count'] / max(stats['tcp_count'], 1),
                'tcp_rst_ratio': stats['tcp_rst_count'] / max(stats['tcp_count'], 1),
                'payload_ratio': stats['payload_bytes'] / stats['total_bytes'] if stats['total_bytes'] > 0 else 0,
                'avg_iat': np.mean(stats['inter_arrival_times']) if stats['inter_arrival_times'] else 0,
                'std_iat': np.std(stats['inter_arrival_times']) if len(stats['inter_arrival_times']) > 1 else 0,
                'std_packet_size': np.std(stats['packet_sizes']) if len(stats['packet_sizes']) > 1 else 0,
            }
            
            features_list.append(features)
        
        return features_list
        
    except Exception as e:
        print(f"Error extracting features from {pcap_path}: {e}")
        return []


def assign_priority_labels(df):
    """
    Assign priority labels based on traffic characteristics
    Priority 0 (Low): Background traffic, low bandwidth
    Priority 1 (Medium): Normal browsing, moderate bandwidth
    Priority 2 (High): Streaming, large transfers, high bandwidth
    """
    priorities = []
    
    for _, row in df.iterrows():
        bps = row['bytes_per_second']
        pps = row['packets_per_second']
        tcp_ratio = row['tcp_ratio']
        payload_ratio = row['payload_ratio']
        
        # High priority: high bandwidth + high payload (streaming/downloads)
        if bps > 500000 and payload_ratio > 0.5:  # >500KB/s with payload
            priorities.append(2)
        # Low priority: low bandwidth + low packet rate
        elif bps < 50000 and pps < 10:  # <50KB/s and <10 pps
            priorities.append(0)
        # Medium priority: everything else
        else:
            priorities.append(1)
    
    return priorities


def process_pcap_directory(pcap_dir, output_csv, ap_mac="02:00:00:00:00:00"):
    """
    Process all PCAP files in directory and create training dataset
    """
    all_features = []
    
    for filename in os.listdir(pcap_dir):
        if filename.endswith('.pcap') or filename.endswith('.pcapng'):
            pcap_path = os.path.join(pcap_dir, filename)
            print(f"Processing {filename}...")
            features = extract_features_from_pcap(pcap_path, ap_mac=ap_mac)
            all_features.extend(features)
    
    if not all_features:
        print("No features extracted!")
        return
    
    df = pd.DataFrame(all_features)
    
    # Assign priority labels
    df['priority'] = assign_priority_labels(df)
    
    # Save to CSV
    df.to_csv(output_csv, index=False)
    print(f"Saved {len(df)} samples to {output_csv}")
    print(f"Priority distribution:\n{df['priority'].value_counts()}")
    
    return df


def train_models(data_csv, output_dir='models'):
    """
    Train RF and IF models from prepared dataset
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Load data
    df = pd.read_csv(data_csv)
    
    # Select feature columns
    feature_cols = [
        'packet_count', 'total_bytes', 'avg_packet_size', 'bytes_per_second',
        'packets_per_second', 'tcp_ratio', 'udp_ratio', 'icmp_ratio',
        'other_ratio', 'unique_dst_ips', 'unique_src_ips', 'unique_dst_ports',
        'unique_src_ports', 'tcp_syn_ratio', 'tcp_fin_ratio', 'tcp_rst_ratio',
        'payload_ratio', 'avg_iat', 'std_iat', 'std_packet_size'
    ]
    
    X = df[feature_cols].values
    
    # Handle NaN/Inf values
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    
    # Train scaler
    print("Training StandardScaler...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train Random Forest for priority classification
    if 'priority' in df.columns:
        print("\nTraining Random Forest Classifier...")
        y_priority = df['priority'].values
        
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y_priority, test_size=0.2, random_state=42, stratify=y_priority
        )
        
        rf = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            class_weight='balanced'
        )
        rf.fit(X_train, y_train)
        
        # Evaluate
        y_pred = rf.predict(X_test)
        print("\nRandom Forest Performance:")
        print(classification_report(y_test, y_pred, target_names=['Low', 'Medium', 'High']))
        print("Confusion Matrix:")
        print(confusion_matrix(y_test, y_pred))
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': rf.feature_importances_
        }).sort_values('importance', ascending=False)
        print("\nTop 10 Important Features:")
        print(feature_importance.head(10))
        
        # Save RF model
        with open(os.path.join(output_dir, 'rf_model.pkl'), 'wb') as f:
            pickle.dump(rf, f)
        print(f"\nSaved RF model to {output_dir}/rf_model.pkl")
    
    # Train Isolation Forest for anomaly detection
    print("\nTraining Isolation Forest...")
    iso_forest = IsolationForest(
        contamination=0.1,  # Assume 10% anomalies
        random_state=42,
        n_estimators=100
    )
    iso_forest.fit(X_scaled)
    
    # Predict anomalies
    anomaly_pred = iso_forest.predict(X_scaled)
    anomaly_count = np.sum(anomaly_pred == -1)
    print(f"Detected {anomaly_count} anomalies ({anomaly_count/len(X)*100:.1f}%)")
    
    # Save IF model
    with open(os.path.join(output_dir, 'if_model.pkl'), 'wb') as f:
        pickle.dump(iso_forest, f)
    print(f"Saved IF model to {output_dir}/if_model.pkl")
    
    # Save scaler
    with open(os.path.join(output_dir, 'scaler.pkl'), 'wb') as f:
        pickle.dump(scaler, f)
    print(f"Saved scaler to {output_dir}/scaler.pkl")
    
    print("\n✓ All models trained and saved!")


def main():
    parser = argparse.ArgumentParser(description='Prepare data and train models')
    parser.add_argument('--mode', choices=['prepare', 'train', 'both'], default='both',
                        help='Mode: prepare data, train models, or both')
    parser.add_argument('--pcap-dir', default='training_pcaps',
                        help='Directory containing PCAP files')
    parser.add_argument('--output-csv', default='training_data.csv',
                        help='Output CSV file for prepared data')
    parser.add_argument('--model-dir', default='models',
                        help='Directory to save trained models')
    parser.add_argument('--ap-mac', default='02:00:00:00:00:00',
                        help='AP MAC address to filter out')
    
    args = parser.parse_args()
    
    if args.mode in ['prepare', 'both']:
        print("=" * 60)
        print("STEP 1: Preparing Dataset from PCAPs")
        print("=" * 60)
        if not os.path.exists(args.pcap_dir):
            print(f"Error: Directory {args.pcap_dir} not found!")
            return
        process_pcap_directory(args.pcap_dir, args.output_csv, args.ap_mac)
    
    if args.mode in ['train', 'both']:
        print("\n" + "=" * 60)
        print("STEP 2: Training ML Models")
        print("=" * 60)
        if not os.path.exists(args.output_csv):
            print(f"Error: Dataset {args.output_csv} not found!")
            return
        train_models(args.output_csv, args.model_dir)


if __name__ == '__main__':
    main()