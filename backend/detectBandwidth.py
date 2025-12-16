#!/usr/bin/env python3
"""
Bandwidth Detection Utility - Improved for Virtual/Wireless Interfaces
"""

import subprocess
import sys
import json
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def detect_interface_bandwidth(interface: str) -> dict:
    """
    Detect bandwidth for a network interface
    Handles physical, virtual, and wireless interfaces
    """
    result = {
        'interface': interface,
        'bandwidth_mbps': None,
        'method': None,
        'raw_output': None,
        'interface_type': None
    }
    
    # First, detect interface type
    result['interface_type'] = _detect_interface_type(interface)
    logger.info(f"Detected interface type: {result['interface_type']}")
    
    # Method 1: ethtool (physical interfaces)
    if result['interface_type'] in ['ethernet', 'unknown']:
        bandwidth = _try_ethtool(interface)
        if bandwidth:
            result['bandwidth_mbps'] = bandwidth
            result['method'] = 'ethtool'
            logger.info(f"✅ Detected {bandwidth} Mbps via ethtool")
            return result
    
    # Method 2: iwconfig (wireless interfaces)
    if result['interface_type'] in ['wireless', 'unknown']:
        bandwidth = _try_iwconfig(interface)
        if bandwidth:
            result['bandwidth_mbps'] = bandwidth
            result['method'] = 'iwconfig'
            logger.info(f"✅ Detected {bandwidth} Mbps via iwconfig")
            return result
    
    # Method 3: iw (modern wireless)
    if result['interface_type'] in ['wireless', 'unknown']:
        bandwidth = _try_iw(interface)
        if bandwidth:
            result['bandwidth_mbps'] = bandwidth
            result['method'] = 'iw'
            logger.info(f"✅ Detected {bandwidth} Mbps via iw")
            return result
    
    # Method 4: For virtual AP interfaces, try to get from physical interface
    if result['interface_type'] == 'virtual_ap':
        bandwidth = _try_get_physical_bandwidth(interface)
        if bandwidth:
            result['bandwidth_mbps'] = bandwidth
            result['method'] = 'physical_interface'
            logger.info(f"✅ Detected {bandwidth} Mbps from physical interface")
            return result
    
    # Method 5: Check interface flags for hints
    bandwidth = _try_interface_flags(interface)
    if bandwidth:
        result['bandwidth_mbps'] = bandwidth
        result['method'] = 'interface_flags'
        logger.info(f"✅ Estimated {bandwidth} Mbps from interface flags")
        return result
    
    # Fallback: Use sensible defaults based on interface type
    if result['interface_type'] == 'virtual_ap':
        # Virtual AP - typically 802.11n (150 Mbps) or 802.11ac (867 Mbps)
        result['bandwidth_mbps'] = 150  # Conservative estimate for 802.11n
        result['method'] = 'default_virtual_ap'
        logger.warning(f"Using default for virtual AP: 150 Mbps")
    elif result['interface_type'] == 'wireless':
        result['bandwidth_mbps'] = 54  # 802.11g baseline
        result['method'] = 'default_wireless'
        logger.warning(f"Using default for wireless: 54 Mbps")
    else:
        result['bandwidth_mbps'] = 100  # Standard Fast Ethernet
        result['method'] = 'default'
        logger.warning(f"Using default: 100 Mbps")
    
    return result


def _detect_interface_type(interface: str) -> str:
    """Detect what type of interface this is"""
    try:
        # Check interface name patterns
        if 'wlan' in interface.lower() or 'wl' in interface.lower():
            if 'ap' in interface.lower():
                return 'virtual_ap'
            return 'wireless'
        elif 'eth' in interface.lower():
            return 'ethernet'
        elif 'enp' in interface.lower() or 'eno' in interface.lower():
            return 'ethernet'
        
        # Check via ip link
        result = subprocess.run(
            f"ip link show {interface}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result.returncode == 0:
            output = result.stdout.lower()
            if 'link/ether' in output:
                if 'master' in output:
                    return 'virtual_ap'
                return 'ethernet'
            elif 'link/ieee802.11' in output:
                return 'wireless'
        
    except Exception as e:
        logger.debug(f"Interface type detection failed: {e}")
    
    return 'unknown'


def _try_ethtool(interface: str) -> int:
    """Try to get speed via ethtool"""
    try:
        result = subprocess.run(
            f"ethtool {interface} 2>/dev/null | grep Speed",
            shell=True,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result.returncode == 0 and "Speed:" in result.stdout:
            # Parse "Speed: 1000Mb/s" or "Speed: 100Mb/s"
            match = re.search(r'Speed:\s*(\d+)Mb/s', result.stdout)
            if match:
                return int(match.group(1))
    except Exception as e:
        logger.debug(f"ethtool failed: {e}")
    return None


def _try_iwconfig(interface: str) -> int:
    """Try to get speed via iwconfig"""
    try:
        result = subprocess.run(
            f"iwconfig {interface} 2>/dev/null",
            shell=True,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result.returncode == 0 and "Bit Rate" in result.stdout:
            # Parse "Bit Rate=54 Mb/s" or "Bit Rate:72.2 Mb/s"
            match = re.search(r'Bit Rate[=:]\s*([\d.]+)\s*Mb/s', result.stdout)
            if match:
                return int(float(match.group(1)))
    except Exception as e:
        logger.debug(f"iwconfig failed: {e}")
    return None


def _try_iw(interface: str) -> int:
    """Try to get speed via iw (modern wireless)"""
    try:
        result = subprocess.run(
            f"iw dev {interface} link 2>/dev/null",
            shell=True,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result.returncode == 0:
            # Parse "tx bitrate: 150.0 MBit/s"
            match = re.search(r'tx bitrate:\s*([\d.]+)\s*MBit/s', result.stdout)
            if match:
                return int(float(match.group(1)))
    except Exception as e:
        logger.debug(f"iw failed: {e}")
    return None


def _try_get_physical_bandwidth(interface: str) -> int:
    """For virtual interfaces, try to get bandwidth from underlying physical interface"""
    try:
        # Check if interface has a master
        result = subprocess.run(
            f"ip link show {interface}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result.returncode == 0:
            # Look for master interface
            match = re.search(r'master\s+(\S+)', result.stdout)
            if match:
                physical_if = match.group(1)
                logger.info(f"Found physical interface: {physical_if}")
                
                # Try to get bandwidth from physical interface
                bandwidth = _try_ethtool(physical_if)
                if bandwidth:
                    return bandwidth
                
                bandwidth = _try_iwconfig(physical_if)
                if bandwidth:
                    return bandwidth
    except Exception as e:
        logger.debug(f"Physical interface detection failed: {e}")
    return None


def _try_interface_flags(interface: str) -> int:
    """Try to estimate bandwidth from interface flags/properties"""
    try:
        result = subprocess.run(
            f"ip -s link show {interface}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result.returncode == 0:
            output = result.stdout
            
            # Check MTU - can give hints
            match = re.search(r'mtu\s+(\d+)', output)
            if match:
                mtu = int(match.group(1))
                if mtu >= 9000:  # Jumbo frames suggest gigabit+
                    return 1000
    except Exception as e:
        logger.debug(f"Interface flags check failed: {e}")
    return None


def set_bandwidth_via_api(bandwidth_mbps: int, host: str = "localhost", port: int = 5000):
    """Set bandwidth via API endpoint"""
    try:
        import requests
        
        url = f"http://{host}:{port}/api/bandwidth/config"
        response = requests.post(url, json={'bandwidth_mbps': bandwidth_mbps})
        
        if response.status_code == 200:
            logger.info(f"✅ Successfully set bandwidth to {bandwidth_mbps} Mbps via API")
            return True
        else:
            logger.error(f"API returned: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to set bandwidth via API: {e}")
        logger.info("Make sure the Flask app is running: sudo python3 app.py")
        return False


def print_recommendations(result: dict):
    """Print recommendations based on detected configuration"""
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    
    if result['method'] == 'default' or result['method'].startswith('default_'):
        print("⚠️  Could not detect actual bandwidth - using default")
        print("\nRecommended actions:")
        print("1. Manually set bandwidth based on your network:")
        print("   - For 802.11n (2.4GHz): 72-150 Mbps")
        print("   - For 802.11n (5GHz): 150-300 Mbps")
        print("   - For 802.11ac: 433-867 Mbps")
        print("   - For 802.11ax (WiFi 6): 600-1200 Mbps")
        print("\n2. Set via environment variable:")
        print(f"   export TOTAL_BANDWIDTH_MBPS=150")
        print("\n3. Set via API:")
        print(f"   curl -X POST http://localhost:5000/api/bandwidth/config \\")
        print(f"     -H 'Content-Type: application/json' \\")
        print(f"     -d '{{\"bandwidth_mbps\": 150}}'")
    else:
        print(f"✅ Successfully detected {result['bandwidth_mbps']} Mbps")
        print(f"   Method: {result['method']}")
        print("\nThis will be used automatically by the system.")
    
    print("="*60 + "\n")


def main():
    """CLI interface"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 detect_bandwidth.py <interface>                    # Detect only")
        print("  python3 detect_bandwidth.py <interface> --set-api          # Detect and set via API")
        print("  python3 detect_bandwidth.py <interface> --set-api --host <host> --port <port>")
        print("\nExamples:")
        print("  python3 detect_bandwidth.py ap1-wlan1")
        print("  python3 detect_bandwidth.py ap1-wlan1 --set-api")
        print("  python3 detect_bandwidth.py eth0 --set-api --host 192.168.1.1 --port 5000")
        sys.exit(1)
    
    interface = sys.argv[1]
    set_api = '--set-api' in sys.argv
    
    # Parse host and port if provided
    host = "localhost"
    port = 5000
    
    try:
        if '--host' in sys.argv:
            idx = sys.argv.index('--host')
            host = sys.argv[idx + 1]
        
        if '--port' in sys.argv:
            idx = sys.argv.index('--port')
            port = int(sys.argv[idx + 1])
    except (IndexError, ValueError) as e:
        print(f"Error parsing arguments: {e}")
        sys.exit(1)
    
    # Detect bandwidth
    print(f"\n🔍 Detecting bandwidth for interface: {interface}\n")
    result = detect_interface_bandwidth(interface)
    
    # Print result as JSON
    print("Result:")
    print(json.dumps(result, indent=2))
    
    # Print recommendations
    print_recommendations(result)
    
    # Set via API if requested
    if set_api and result['bandwidth_mbps']:
        print(f"📡 Setting bandwidth via API ({host}:{port})...")
        success = set_bandwidth_via_api(result['bandwidth_mbps'], host, port)
        if success:
            print("✅ Bandwidth configured successfully!\n")
        else:
            print("❌ Failed to configure via API\n")
            sys.exit(1)


if __name__ == "__main__":
    main()