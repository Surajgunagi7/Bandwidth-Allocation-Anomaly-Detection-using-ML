#!/usr/bin/env python3
"""
Quick test script for dataset generation
Tests a single scenario to verify everything works
"""

import subprocess
import time
import os
import signal
from pathlib import Path

def test_single_capture():
    """Test capturing a single PCAP file"""
    
    print("="*60)
    print("TESTING DATASET GENERATION")
    print("="*60)
    
    # Setup
    pcap_dir = Path("./training_data/pcap_captures")
    pcap_dir.mkdir(exist_ok=True, parents=True)
    pcap_output = pcap_dir / "test_capture.pcap"
    
    # Remove old test file
    if pcap_output.exists():
        pcap_output.unlink()
    
    print(f"\n1. PCAP will be saved to: {pcap_output}")
    
    # Clean up
    print("\n2. Cleaning up previous Mininet instances...")
    subprocess.run("sudo mn -c 2>/dev/null", shell=True)
    time.sleep(2)
    
    # Get topology path
    topo_path = Path(__file__).parent.parent / "mininet" / "dataset_topology.py"
    if not topo_path.exists():
        print(f"✗ ERROR: dataset_topology.py not found at {topo_path}")
        return False
    
    print(f"   ✓ Found topology: {topo_path}")
    
    # Start Mininet
    print("\n3. Starting Mininet-WiFi...")
    mininet_proc = subprocess.Popen(
        ["sudo", "python3", str(topo_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    print("   Waiting 12 seconds for network initialization...")
    time.sleep(12)
    
    # Check interface
    print("\n4. Checking ap1-wlan1 interface...")
    check = subprocess.run(
        "ip link show ap1-wlan1",
        shell=True,
        capture_output=True,
        text=True
    )
    
    if check.returncode != 0:
        print("✗ ERROR: ap1-wlan1 interface not found!")
        mininet_proc.terminate()
        return False
    
    print("   ✓ ap1-wlan1 interface exists")
    
    # Start tcpdump
    print("\n5. Starting tcpdump...")
    tcpdump_proc = subprocess.Popen(
        f"sudo tcpdump -i ap1-wlan1 -w {pcap_output} -c 100",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    time.sleep(2)
    print("   ✓ tcpdump started")
    
    # Generate traffic
    print("\n6. Generating test traffic (ping)...")
    
    # Get sta1 PID
    sta1_pid_result = subprocess.run(
        "pgrep -f 'mininet:sta1'",
        shell=True,
        capture_output=True,
        text=True
    )
    
    sta1_pid = sta1_pid_result.stdout.strip()
    
    if sta1_pid:
        print(f"   ✓ Found sta1 PID: {sta1_pid}")
        subprocess.run(
            f"sudo mnexec -a {sta1_pid} ping -c 20 10.0.0.3 &",
            shell=True
        )
        print("   ✓ Traffic generation started")
    else:
        print("   ✗ Could not find sta1 PID")
        tcpdump_proc.terminate()
        mininet_proc.terminate()
        return False
    
    # Wait for traffic
    print("\n7. Waiting 25 seconds for traffic...")
    time.sleep(25)
    
    # Stop tcpdump
    print("\n8. Stopping tcpdump...")
    tcpdump_proc.send_signal(signal.SIGINT)
    time.sleep(2)
    tcpdump_proc.terminate()
    
    # Stop Mininet
    print("\n9. Stopping Mininet...")
    mininet_proc.terminate()
    subprocess.run("sudo mn -c 2>/dev/null", shell=True)
    time.sleep(3)
    
    # Check results
    print("\n10. Checking results...")
    if pcap_output.exists():
        size = pcap_output.stat().st_size
        print(f"    ✓ PCAP file created: {size} bytes")
        
        if size > 24:  # Valid PCAP header
            print(f"    ✓ PCAP appears valid")
            
            # Try to read packets
            try:
                packet_count = subprocess.run(
                    f"tcpdump -r {pcap_output} -n | wc -l",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                count = packet_count.stdout.strip()
                print(f"    ✓ PCAP contains {count} packets")
                
                print("\n" + "="*60)
                print("✓ TEST PASSED!")
                print("="*60)
                print("\nYou can now run the full dataset generator:")
                print("  sudo python3 dataset_generator.py")
                return True
                
            except Exception as e:
                print(f"    ✗ Error reading PCAP: {e}")
                return False
        else:
            print(f"    ✗ PCAP file too small (only {size} bytes)")
            return False
    else:
        print("    ✗ PCAP file not created")
        return False

if __name__ == "__main__":
    import sys
    
    # Check if running from training directory
    if not Path("dataset_generator.py").exists():
        print("ERROR: Run this from the training/ directory!")
        sys.exit(1)
    
    try:
        success = test_single_capture()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        subprocess.run("sudo mn -c 2>/dev/null", shell=True)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        subprocess.run("sudo mn -c 2>/dev/null", shell=True)
        sys.exit(1)