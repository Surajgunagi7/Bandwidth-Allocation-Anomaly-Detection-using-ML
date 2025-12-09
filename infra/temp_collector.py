"""
Traffic Collector for Mininet-WiFi
Captures traffic on AP interface and sends to backend
"""

import subprocess
import time
import requests
import os
import sys
import logging
from datetime import datetime

# Configuration
AP_INTERFACE = "ap1-wlan1"  # Adjust based on your topology
CAPTURE_DURATION = 3  # seconds
BACKEND_URL = "http://localhost:5000/traffic"
TEMP_DIR = "/tmp/traffic_captures"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create temp directory
os.makedirs(TEMP_DIR, exist_ok=True)


def check_interface_exists(interface):
    """Check if network interface exists"""
    result = subprocess.run(
        f"ip link show {interface}",
        shell=True,
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def capture_traffic(interface, duration, output_file):
    """
    Capture traffic using tcpdump
    Returns True if successful, False otherwise
    """
    try:
        cmd = [
            "tcpdump",
            "-i", interface,
            "-w", output_file,
            "-G", str(duration),
            "-W", "1",
            "-Z", "root"
        ]
        
        logger.info(f"Starting capture on {interface} for {duration}s...")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration + 5
        )
        
        # Check if file was created and has data
        if os.path.exists(output_file) and os.path.getsize(output_file) > 24:
            logger.info(f"Captured {os.path.getsize(output_file)} bytes")
            return True
        else:
            logger.warning("No traffic captured or file empty")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Capture timeout")
        return False
    except Exception as e:
        logger.error(f"Capture error: {e}")
        return False


def send_to_backend(pcap_file):
    """
    Send PCAP file to backend via HTTP POST
    """
    try:
        with open(pcap_file, 'rb') as f:
            files = {'pcap': (os.path.basename(pcap_file), f, 'application/vnd.tcpdump.pcap')}
            
            response = requests.post(
                BACKEND_URL,
                files=files,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully sent to backend: {response.json()}")
                return True
            else:
                logger.error(f"Backend error: {response.status_code} - {response.text}")
                return False
                
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to backend - is it running?")
        return False
    except requests.exceptions.Timeout:
        logger.error("Backend request timeout")
        return False
    except Exception as e:
        logger.error(f"Error sending to backend: {e}")
        return False


def cleanup_old_files(directory, max_age_seconds=300):
    """
    Remove old capture files to prevent disk fill
    """
    try:
        now = time.time()
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                age = now - os.path.getmtime(filepath)
                if age > max_age_seconds:
                    os.remove(filepath)
                    logger.debug(f"Cleaned up old file: {filename}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


def main():
    logger.info("=" * 60)
    logger.info("Traffic Collector Starting")
    logger.info("=" * 60)
    logger.info(f"Interface: {AP_INTERFACE}")
    logger.info(f"Capture Duration: {CAPTURE_DURATION}s")
    logger.info(f"Backend URL: {BACKEND_URL}")
    logger.info("=" * 60)
    
    # Check if interface exists
    if not check_interface_exists(AP_INTERFACE):
        logger.error(f"Interface {AP_INTERFACE} not found!")
        logger.error("Available interfaces:")
        subprocess.run("ip link show", shell=True)
        sys.exit(1)
    
    # Check if backend is reachable
    try:
        response = requests.get(BACKEND_URL.replace('/traffic', '/status'), timeout=5)
        logger.info(f"Backend is reachable: {response.json()}")
    except Exception as e:
        logger.warning(f"Backend not reachable (will retry): {e}")
    
    capture_count = 0
    error_count = 0
    
    logger.info("\nStarting capture loop (Ctrl+C to stop)...\n")
    
    try:
        while True:
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pcap_file = os.path.join(TEMP_DIR, f"capture_{timestamp}.pcap")
            
            # Capture traffic
            if capture_traffic(AP_INTERFACE, CAPTURE_DURATION, pcap_file):
                # Send to backend
                if send_to_backend(pcap_file):
                    capture_count += 1
                    error_count = 0  # Reset error count on success
                else:
                    error_count += 1
                
                # Remove local file after sending
                try:
                    os.remove(pcap_file)
                except:
                    pass
            else:
                logger.warning("Skipping empty capture")
                error_count += 1
            
            # Periodic cleanup
            if capture_count % 20 == 0:
                cleanup_old_files(TEMP_DIR)
            
            # Exit if too many consecutive errors
            if error_count >= 10:
                logger.error("Too many consecutive errors - exiting")
                sys.exit(1)
            
            # Log status
            if capture_count % 10 == 0 and capture_count > 0:
                logger.info(f"Status: {capture_count} captures sent successfully")
            
            # Small delay before next capture
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        logger.info("\n\nStopping collector...")
        logger.info(f"Total captures sent: {capture_count}")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        cleanup_old_files(TEMP_DIR, max_age_seconds=0)
        logger.info("Collector stopped")


if __name__ == '__main__':
    # Check if running as root (needed for tcpdump)
    if os.geteuid() != 0:
        logger.error("This script must be run as root (for tcpdump)")
        logger.info("Try: sudo python3 collector.py")
        sys.exit(1)
    
    main()