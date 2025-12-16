#!/usr/bin/env python3
"""
Bandwidth Detection Utility
Can be run standalone or imported
"""

import subprocess
import sys
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def detect_interface_bandwidth(interface: str) -> dict:
    """
    Detect bandwidth for a network interface
    Returns dict with bandwidth info
    """
    result = {
        'interface': interface,
        'bandwidth_mbps': None,
        'method': None,
        'raw_output': None
    }
    
    # Method 1: ethtool
    try:
        cmd_result = subprocess.run(
            f"ethtool {interface} 2>/dev/null | grep Speed",
            shell=True,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if cmd_result.returncode == 0 and "Speed:" in cmd_result.stdout:
            result['raw_output'] = cmd_result.stdout.strip()
            
            # Parse "Speed: 1000Mb/s" or "Speed: 100Mb/s"
            if "Mb/s" in cmd_result.stdout:
                speed_str = cmd_result.stdout.split("Speed:")[1].strip()
                speed_str = speed_str.replace("Mb/s", "").strip()
                
                try:
                    bandwidth = int(speed_str)
                    result['bandwidth_mbps'] = bandwidth
                    result['method'] = 'ethtool'
                    logger.info(f"✅ Detected {bandwidth} Mbps via ethtool")
                    return result
                except ValueError:
                    pass
    except Exception as e:
        logger.debug(f"ethtool failed: {e}")
    
    # Method 2: iwconfig (wireless)
    try:
        cmd_result = subprocess.run(
            f"iwconfig {interface} 2>/dev/null | grep 'Bit Rate'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if cmd_result.returncode == 0 and "Bit Rate" in cmd_result.stdout:
            result['raw_output'] = cmd_result.stdout.strip()
            
            # Parse "Bit Rate=54 Mb/s" or "Bit Rate:72.2 Mb/s"
            if "Mb/s" in cmd_result.stdout:
                # Handle both = and : separators
                rate_part = cmd_result.stdout.split("Bit Rate")[1]
                rate_part = rate_part.replace("=", ":").split(":")[1]
                rate_str = rate_part.split("Mb/s")[0].strip()
                
                try:
                    bandwidth = int(float(rate_str))
                    result['bandwidth_mbps'] = bandwidth
                    result['method'] = 'iwconfig'
                    logger.info(f"✅ Detected {bandwidth} Mbps via iwconfig")
                    return result
                except ValueError:
                    pass
    except Exception as e:
        logger.debug(f"iwconfig failed: {e}")
    
    # Method 3: ip link show (check if interface is up)
    try:
        cmd_result = subprocess.run(
            f"ip link show {interface} 2>/dev/null",
            shell=True,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if cmd_result.returncode == 0:
            result['raw_output'] = cmd_result.stdout
            logger.info(f"Interface {interface} exists but bandwidth detection failed")
    except Exception as e:
        logger.error(f"Interface {interface} not found: {e}")
    
    # Fallback
    logger.warning(f"Could not detect bandwidth for {interface}, using default 100 Mbps")
    result['bandwidth_mbps'] = 100
    result['method'] = 'default'
    
    return result


def set_bandwidth_via_api(bandwidth_mbps: int, host: str = "localhost", port: int = 5000):
    """
    Set bandwidth via API endpoint
    """
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
        return False


def main():
    """CLI interface"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python detect_bandwidth.py <interface>               # Detect only")
        print("  python detect_bandwidth.py <interface> --set-api     # Detect and set via API")
        print("  python detect_bandwidth.py <interface> --set-api --host <host> --port <port>")
        sys.exit(1)
    
    interface = sys.argv[1]
    set_api = '--set-api' in sys.argv
    
    # Parse host and port if provided
    host = "localhost"
    port = 5000
    
    if '--host' in sys.argv:
        idx = sys.argv.index('--host')
        host = sys.argv[idx + 1]
    
    if '--port' in sys.argv:
        idx = sys.argv.index('--port')
        port = int(sys.argv[idx + 1])
    
    # Detect bandwidth
    result = detect_interface_bandwidth(interface)
    
    # Print result
    print(json.dumps(result, indent=2))
    
    # Set via API if requested
    if set_api and result['bandwidth_mbps']:
        set_bandwidth_via_api(result['bandwidth_mbps'], host, port)


if __name__ == "__main__":
    main()