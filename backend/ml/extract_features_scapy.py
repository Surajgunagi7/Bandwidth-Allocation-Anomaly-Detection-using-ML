#!/usr/bin/env python3
"""
extract_features_scapy.py

Scans all .pcap files in a directory, groups packets by MAC address,
aggregates into fixed-length time windows (default 3s) and extracts
features per (mac, window_start).

Outputs dataset_by_mac.parquet and dataset_by_mac.csv.

Usage:
  python extract_features_scapy.py --pcap_dir ./datasets --out dataset_by_mac.parquet --window 3

Requires: scapy, pandas, pyarrow (optional), tqdm
"""
import os
import argparse
from scapy.utils import RawPcapReader
from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, TCP, UDP, ICMP
import pandas as pd
import math
from collections import defaultdict, Counter
from tqdm import tqdm
import warnings
warnings.filterwarnings("ignore")

def tuple_flow(pkt):
    """Return a tuple identifying a flow where applicable, else None."""
    try:
        if IP in pkt:
            ip = pkt[IP]
            proto = None
            sport = dport = 0
            if TCP in pkt:
                proto = 'TCP'
                sport = pkt[TCP].sport
                dport = pkt[TCP].dport
            elif UDP in pkt:
                proto = 'UDP'
                sport = pkt[UDP].sport
                dport = pkt[UDP].dport
            elif ICMP in pkt:
                proto = 'ICMP'
            else:
                proto = str(ip.proto)
            return (ip.src, ip.dst, sport, dport, proto)
    except Exception:
        return None
    return None

def safe_len(pkt):
    """Safely get packet length."""
    try:
        return len(pkt)
    except Exception:
        return 0

def process_pcaps(pcap_dir, window_size=3.0):
    """Process all pcap files and extract features."""
    # Data structures for each (mac, window_start)
    feats = defaultdict(lambda: {
        'total_bytes': 0,
        'total_pkts': 0,
        'bytes_out': 0,
        'bytes_in': 0,
        'pkts_out': 0,
        'pkts_in': 0,
        'pkt_sizes': [],
        'iat_list': [],
        'last_ts': None,
        'flow_set': set(),
        'proto_counts': Counter(),
        'dst_set': set(),
    })

    global_first_ts = None
    
    # Find all pcap files
    pcap_files = sorted([
        os.path.join(pcap_dir, f) 
        for f in os.listdir(pcap_dir) 
        if f.lower().endswith(('.pcap', '.pcapng', '.pcap.gz'))
    ])
    
    if not pcap_files:
        raise SystemExit(f"No pcap files found in {pcap_dir}")

    print(f"Found {len(pcap_files)} pcap files:")
    for pf in pcap_files:
        print(f"  - {os.path.basename(pf)}")

    # First pass: determine earliest timestamp
    print("\nScanning pcaps to find first timestamp...")
    for p in pcap_files:
        try:
            for pkt_data, meta in RawPcapReader(p):
                pkt_time = float(meta.sec) + float(meta.usec)/1e6
                if global_first_ts is None:
                    global_first_ts = pkt_time
                else:
                    global_first_ts = min(global_first_ts, pkt_time)
                break
        except Exception as e:
            print(f"  Warning: Could not read {os.path.basename(p)}: {e}")
            continue
    
    if global_first_ts is None:
        raise SystemExit("Could not determine any packet timestamps in pcaps.")

    print(f"Global first timestamp: {global_first_ts:.6f}")

    # Second pass: process all packets
    print(f"\nProcessing packets and aggregating into {window_size:.1f}s windows...")
    total_packets = 0
    
    for p in pcap_files:
        print(f"\n -> Processing: {os.path.basename(p)}")
        try:
            reader = RawPcapReader(p)
        except Exception as e:
            print(f"   Failed to open {p}: {e}")
            continue

        pkt_count = 0
        for pkt_data, meta in tqdm(reader, desc=os.path.basename(p), unit="pkt"):
            try:
                pkt = Ether(pkt_data)
            except Exception:
                continue

            pkt_count += 1
            total_packets += 1

            # Get timestamp and compute window
            ts = float(meta.sec) + float(meta.usec)/1e6
            widx = math.floor((ts - global_first_ts) / window_size)
            window_start = global_first_ts + widx * window_size

            # Get MAC addresses
            if not hasattr(pkt, 'src') or not hasattr(pkt, 'dst'):
                continue
            
            src_mac = pkt.src.lower()
            dst_mac = pkt.dst.lower()
            pkt_len = safe_len(pkt)

            # Determine protocol
            proto_name = 'OTHER'
            if IP in pkt:
                if TCP in pkt:
                    proto_name = 'TCP'
                elif UDP in pkt:
                    proto_name = 'UDP'
                elif ICMP in pkt:
                    proto_name = 'ICMP'
                else:
                    proto_name = 'IP'

            # Update features for source MAC
            key_src = (src_mac, window_start)
            s = feats[key_src]
            s['total_bytes'] += pkt_len
            s['total_pkts'] += 1
            s['bytes_out'] += pkt_len
            s['pkts_out'] += 1
            s['pkt_sizes'].append(pkt_len)
            s['proto_counts'][proto_name] += 1
            s['dst_set'].add(dst_mac)
            
            # Track flows
            fl = tuple_flow(pkt)
            if fl:
                s['flow_set'].add(fl)
            
            # Calculate inter-arrival time
            if s['last_ts'] is not None:
                s['iat_list'].append(ts - s['last_ts'])
            s['last_ts'] = ts

            # Update features for destination MAC
            key_dst = (dst_mac, window_start)
            d = feats[key_dst]
            d['total_bytes'] += pkt_len
            d['total_pkts'] += 1
            d['bytes_in'] += pkt_len
            d['pkts_in'] += 1
            d['pkt_sizes'].append(pkt_len)
            d['proto_counts'][proto_name] += 1
            d['dst_set'].add(src_mac)
            
            if fl:
                d['flow_set'].add(fl)
            
            if d['last_ts'] is not None:
                d['iat_list'].append(ts - d['last_ts'])
            d['last_ts'] = ts

        reader.close()
        print(f"   Processed {pkt_count} packets")

    print(f"\nTotal packets processed: {total_packets}")
    print(f"Total MAC-window combinations: {len(feats)}")

    # Build feature dataframe
    print("\nBuilding feature table...")
    rows = []
    
    for (mac, window_start), d in feats.items():
        total_pkts = d['total_pkts']
        if total_pkts == 0:
            continue

        pkt_sizes = d['pkt_sizes']
        iat = d['iat_list'] if d['iat_list'] else [0.0]
        
        # Calculate statistics
        avg_pkt_size = sum(pkt_sizes) / len(pkt_sizes) if pkt_sizes else 0.0
        std_pkt_size = pd.Series(pkt_sizes).std() if len(pkt_sizes) > 1 else 0.0
        std_pkt_size = 0.0 if pd.isna(std_pkt_size) else float(std_pkt_size)
        
        iat_mean = sum(iat) / len(iat) if iat else 0.0
        iat_std = pd.Series(iat).std() if len(iat) > 1 else 0.0
        iat_std = 0.0 if pd.isna(iat_std) else float(iat_std)
        
        flows = len(d['flow_set'])
        unique_dsts = len(d['dst_set'])
        
        # Protocol counts
        proto_tcp = d['proto_counts'].get('TCP', 0)
        proto_udp = d['proto_counts'].get('UDP', 0)
        proto_icmp = d['proto_counts'].get('ICMP', 0)
        proto_other = total_pkts - (proto_tcp + proto_udp + proto_icmp)

        # Derived metrics
        burstiness = (max(pkt_sizes) / (avg_pkt_size + 1e-9)) if pkt_sizes else 0.0
        bytes_per_sec = d['total_bytes'] / window_size
        pkts_per_sec = total_pkts / window_size

        row = {
            'mac': mac,
            'window_start': window_start,
            'window_size_s': window_size,
            'total_bytes': d['total_bytes'],
            'total_pkts': total_pkts,
            'bytes_out': d['bytes_out'],
            'bytes_in': d['bytes_in'],
            'pkts_out': d['pkts_out'],
            'pkts_in': d['pkts_in'],
            'bytes_per_sec': bytes_per_sec,
            'pkts_per_sec': pkts_per_sec,
            'avg_pkt_size': avg_pkt_size,
            'std_pkt_size': std_pkt_size,
            'iat_mean': iat_mean,
            'iat_std': iat_std,
            'flow_count': flows,
            'unique_dest_count': unique_dsts,
            'tcp_pkts': proto_tcp,
            'udp_pkts': proto_udp,
            'icmp_pkts': proto_icmp,
            'other_pkts': proto_other,
            'burstiness': burstiness,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    
    if df.empty:
        print("No features extracted (empty dataframe).")
        return df

    # Sort and add rolling statistics
    df = df.sort_values(['mac', 'window_start']).reset_index(drop=True)
    
    print(f"Extracted features for {df['mac'].nunique()} unique MAC addresses")
    print(f"Total feature vectors: {len(df)}")
    
    # Rolling window statistics per MAC
    df['bytes_roll_mean_3'] = (
        df.groupby('mac')['bytes_per_sec']
        .rolling(3, min_periods=1)
        .mean()
        .reset_index(0, drop=True)
    )
    df['bytes_roll_std_3'] = (
        df.groupby('mac')['bytes_per_sec']
        .rolling(3, min_periods=1)
        .std()
        .reset_index(0, drop=True)
        .fillna(0.0)
    )

    return df

def main():
    parser = argparse.ArgumentParser(
        description='Extract ML features from network pcap files'
    )
    parser.add_argument(
        '--pcap_dir', 
        default='./datasets', 
        help='Directory containing pcap files (default: ./datasets)'
    )
    parser.add_argument(
        '--out', 
        default='dataset_by_mac.parquet', 
        help='Output file path (default: dataset_by_mac.parquet)'
    )
    parser.add_argument(
        '--window', 
        type=float, 
        default=3.0, 
        help='Time window size in seconds (default: 3.0)'
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PCAP Feature Extraction for ML")
    print("=" * 60)
    print(f"PCAP Directory: {args.pcap_dir}")
    print(f"Output File: {args.out}")
    print(f"Window Size: {args.window}s")
    print("=" * 60)

    # Process pcaps
    df = process_pcaps(args.pcap_dir, window_size=args.window)

    if df is None or df.empty:
        print("\nNo data to write.")
        return

    # Write output files
    print("\nWriting output files...")
    out = args.out
    
    try:
        df.to_parquet(out, index=False)
        print(f"✓ Wrote Parquet: {out}")
        
        # Also write CSV
        csv_out = os.path.splitext(out)[0] + '.csv'
        df.to_csv(csv_out, index=False)
        print(f"✓ Wrote CSV: {csv_out}")
        
    except Exception as e:
        print(f"Parquet write failed ({e}). Falling back to CSV only.")
        csv_out = os.path.splitext(out)[0] + '.csv'
        df.to_csv(csv_out, index=False)
        print(f"✓ Wrote CSV: {csv_out}")

    # Display summary
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"Features extracted: {len(df.columns)}")
    print(f"Total records: {len(df)}")
    print(f"Unique MACs: {df['mac'].nunique()}")
    print(f"Time windows: {df['window_start'].nunique()}")
    print("\nFeature columns:")
    for col in df.columns:
        print(f"  - {col}")

if __name__ == '__main__':
    main()