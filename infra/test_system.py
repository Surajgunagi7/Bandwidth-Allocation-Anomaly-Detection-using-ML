"""
Test script to verify the complete system works
Run this BEFORE integrating with Mininet-WiFi
"""

import requests
import os
import numpy as np
import pandas as pd
from scapy.all import wrpcap, Ether, IP, TCP, UDP, Raw
import time
import sys

BASE_URL = "http://localhost:5000"

def print_status(message, success=True):
    """Print colored status message"""
    color = "\033[92m" if success else "\033[91m"
    reset = "\033[0m"
    symbol = "✓" if success else "✗"
    print(f"{color}[{symbol}] {message}{reset}")


def check_backend():
    """Check if backend is running"""
    try:
        response = requests.get(f"{BASE_URL}/status", timeout=5)
        if response.status_code == 200:
            print_status("Backend is running")
            print(f"    Status: {response.json()}")
            return True
        else:
            print_status(f"Backend returned status {response.status_code}", False)
            return False
    except requests.exceptions.ConnectionError:
        print_status("Backend is not running!", False)
        print("    Start it with: python3 app.py")
        return False
    except Exception as e:
        print_status(f"Error checking backend: {e}", False)
        return False


def check_models():
    """Check if models exist"""
    model_files = ['models/rf_model.pkl', 'models/if_model.pkl', 'models/scaler.pkl']
    all_exist = all(os.path.exists(f) for f in model_files)
    
    if all_exist:
        print_status("ML models found")
        for f in model_files:
            size = os.path.getsize(f) / 1024
            print(f"    {f}: {size:.1f} KB")
        return True
    else:
        print_status("ML models not found!", False)
        print("    Train models with: python3 data_preparation.py --mode train")
        return False


def generate_test_pcap(filename, num_packets=100):
    """Generate a synthetic PCAP for testing"""
    packets = []
    
    src_mac = "00:00:00:00:00:01"
    dst_mac = "00:00:00:00:00:02"
    src_ip = "10.0.0.1"
    dst_ip = "10.0.0.2"
    
    for i in range(num_packets):
        # Mix of TCP and UDP
        if i % 3 == 0:
            # UDP packet
            pkt = Ether(src=src_mac, dst=dst_mac) / \
                  IP(src=src_ip, dst=dst_ip) / \
                  UDP(sport=12345, dport=80) / \
                  Raw(load=b"A" * np.random.randint(100, 1400))
        else:
            # TCP packet
            flags = 'S' if i % 10 == 0 else 'A'
            pkt = Ether(src=src_mac, dst=dst_mac) / \
                  IP(src=src_ip, dst=dst_ip) / \
                  TCP(sport=12345, dport=80, flags=flags) / \
                  Raw(load=b"B" * np.random.randint(100, 1400))
        
        packets.append(pkt)
    
    wrpcap(filename, packets)
    print_status(f"Generated test PCAP: {filename}")
    print(f"    {num_packets} packets, {os.path.getsize(filename)} bytes")
    return True


def test_traffic_endpoint():
    """Test sending traffic to backend"""
    pcap_file = "/tmp/test_traffic.pcap"
    
    # Generate test PCAP
    generate_test_pcap(pcap_file)
    
    # Send to backend
    try:
        with open(pcap_file, 'rb') as f:
            files = {'pcap': ('test.pcap', f, 'application/vnd.tcpdump.pcap')}
            response = requests.post(f"{BASE_URL}/traffic", files=files, timeout=10)
        
        if response.status_code == 200:
            print_status("Traffic endpoint working")
            result = response.json()
            print(f"    Processed MACs: {result.get('macs_processed', [])}")
            return True
        else:
            print_status(f"Traffic endpoint failed: {response.status_code}", False)
            print(f"    {response.text}")
            return False
            
    except Exception as e:
        print_status(f"Error testing traffic endpoint: {e}", False)
        return False
    finally:
        if os.path.exists(pcap_file):
            os.remove(pcap_file)


def test_allocations():
    """Test bandwidth allocation endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/allocations", timeout=5)
        if response.status_code == 200:
            allocations = response.json()
            print_status("Allocations endpoint working")
            if allocations:
                print("    Current allocations:")
                for mac, bw in allocations.items():
                    print(f"      {mac}: {bw} Mbps")
            else:
                print("    No active allocations yet")
            return True
        else:
            print_status(f"Allocations endpoint failed: {response.status_code}", False)
            return False
    except Exception as e:
        print_status(f"Error testing allocations: {e}", False)
        return False


def test_model_training():
    """Test model training with synthetic data"""
    print("\nGenerating synthetic training data...")
    
    # Generate synthetic dataset
    np.random.seed(42)
    n_samples = 100
    
    data = {
        'packet_count': np.random.randint(10, 1000, n_samples),
        'total_bytes': np.random.randint(1000, 1000000, n_samples),
        'avg_packet_size': np.random.randint(64, 1500, n_samples),
        'bytes_per_second': np.random.randint(1000, 500000, n_samples),
        'packets_per_second': np.random.randint(5, 300, n_samples),
        'tcp_ratio': np.random.random(n_samples),
        'udp_ratio': np.random.random(n_samples),
        'icmp_ratio': np.random.random(n_samples) * 0.1,
        'other_ratio': np.random.random(n_samples) * 0.1,
        'unique_dst_ips': np.random.randint(1, 50, n_samples),
        'unique_src_ips': np.random.randint(1, 5, n_samples),
        'unique_dst_ports': np.random.randint(1, 100, n_samples),
        'unique_src_ports': np.random.randint(1, 20, n_samples),
        'tcp_syn_ratio': np.random.random(n_samples) * 0.3,
        'tcp_fin_ratio': np.random.random(n_samples) * 0.2,
        'tcp_rst_ratio': np.random.random(n_samples) * 0.1,
        'payload_ratio': np.random.random(n_samples),
        'avg_iat': np.random.random(n_samples) * 0.1,
        'std_iat': np.random.random(n_samples) * 0.05,
        'std_packet_size': np.random.randint(0, 500, n_samples),
    }
    
    # Assign priority labels
    priorities = []
    for i in range(n_samples):
        if data['bytes_per_second'][i] > 200000:
            priorities.append(2)
        elif data['bytes_per_second'][i] < 50000:
            priorities.append(0)
        else:
            priorities.append(1)
    
    data['priority'] = priorities
    df = pd.DataFrame(data)
    
    test_csv = '/tmp/test_training_data.csv'
    df.to_csv(test_csv, index=False)
    
    print_status(f"Created synthetic dataset with {n_samples} samples")
    print(f"    Priority distribution: {dict(df['priority'].value_counts())}")
    
    # Test training endpoint
    try:
        with open(test_csv, 'rb') as f:
            files = {'data': ('training_data.csv', f, 'text/csv')}
            response = requests.post(f"{BASE_URL}/train", files=files, timeout=30)
        
        if response.status_code == 200:
            print_status("Model training successful")
            print(f"    {response.json()}")
            return True
        else:
            print_status(f"Model training failed: {response.status_code}", False)
            print(f"    {response.text}")
            return False
            
    except Exception as e:
        print_status(f"Error training models: {e}", False)
        return False
    finally:
        if os.path.exists(test_csv):
            os.remove(test_csv)


def stress_test():
    """Send multiple traffic samples rapidly"""
    print("\nRunning stress test (10 requests)...")
    success_count = 0
    
    for i in range(10):
        pcap_file = f"/tmp/stress_test_{i}.pcap"
        generate_test_pcap(pcap_file, num_packets=50)
        
        try:
            with open(pcap_file, 'rb') as f:
                files = {'pcap': (f'stress_{i}.pcap', f, 'application/vnd.tcpdump.pcap')}
                response = requests.post(f"{BASE_URL}/traffic", files=files, timeout=5)
            
            if response.status_code == 200:
                success_count += 1
                sys.stdout.write('.')
                sys.stdout.flush()
            else:
                sys.stdout.write('x')
                sys.stdout.flush()
        except:
            sys.stdout.write('x')
            sys.stdout.flush()
        finally:
            if os.path.exists(pcap_file):
                os.remove(pcap_file)
        
        time.sleep(0.3)
    
    print()
    if success_count >= 8:
        print_status(f"Stress test passed ({success_count}/10 succeeded)")
        return True
    else:
        print_status(f"Stress test failed ({success_count}/10 succeeded)", False)
        return False


def main():
    print("=" * 60)
    print("BANDWIDTH ALLOCATION & ANOMALY DETECTION - SYSTEM TEST")
    print("=" * 60)
    print()
    
    tests = [
        ("Backend Connectivity", check_backend),
        ("Model Files", check_models),
        ("Traffic Endpoint", test_traffic_endpoint),
        ("Allocations Endpoint", test_allocations),
        ("Model Training", test_model_training),
        ("Stress Test", stress_test),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'─' * 60}")
        print(f"Testing: {test_name}")
        print('─' * 60)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_status(f"Test crashed: {e}", False)
            results.append((test_name, False))
        time.sleep(1)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print_status(f"{test_name}: {status}", result)
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print_status("\n🎉 All tests passed! System is ready.", True)
        print("\nNext steps:")
        print("  1. Start your Mininet-WiFi topology")
        print("  2. Run: sudo python3 collector.py")
        print("  3. Generate traffic in Mininet")
        print("  4. Monitor: curl http://localhost:5000/allocations")
    else:
        print_status(f"\n⚠️  {total - passed} test(s) failed. Fix issues before proceeding.", False)
        return 1
    
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)