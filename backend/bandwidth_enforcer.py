#!/usr/bin/env python3
"""
Bandwidth Enforcement Module - FIXED VERSION
Fixes: TC initialization errors, better error handling, permission checks
"""

import subprocess
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import time
import json
from config import Config
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BandwidthAllocation:
    """Represents bandwidth allocation for a device"""
    mac_address: str
    allocated_bw_kbps: int  # Kilobits per second
    priority: int  # 1 (highest) to 3 (lowest)
    device_ip: Optional[str] = None


class TrafficController:
    """Manages Linux TC (Traffic Control) commands for bandwidth shaping"""
    
    def __init__(self, interface: str = "ap1-wlan1"):
        """
        Initialize Traffic Controller
        
        Args:
            interface: Network interface name (e.g., ap1-wlan1 in Mininet-WiFi)
        """
        self.interface = interface
        self.active_allocations: Dict[str, BandwidthAllocation] = {}
        self.root_handle = "1:"
        self.initialized = False
        
        # Verify interface exists
        if not self._verify_interface():
            logger.error(f"❌ Interface {interface} not found!")
            logger.info("Available interfaces:")
            self._list_interfaces()
        
        # Check TC permissions
        if not self._check_tc_permissions():
            logger.error("❌ Insufficient permissions for TC commands")
            logger.info("Run with: sudo python app.py")
    
    def _verify_interface(self) -> bool:
        """Verify network interface exists"""
        try:
            result = subprocess.run(
                f"ip link show {self.interface}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to verify interface: {e}")
            return False
    
    def _list_interfaces(self):
        """List available network interfaces"""
        try:
            result = subprocess.run(
                "ip link show",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.info(f"Interfaces:\n{result.stdout}")
        except Exception as e:
            logger.error(f"Failed to list interfaces: {e}")
    
    def _check_tc_permissions(self) -> bool:
        """Check if we have permissions to run TC commands"""
        try:
            # Try a harmless TC command
            result = subprocess.run(
                "tc qdisc show",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"TC permission check failed: {e}")
            return False
    
    def initialize_qdisc(self, total_bandwidth_mbps: int = None):
        """
        Initialize HTB (Hierarchical Token Bucket) qdisc on interface
        FIXED: Better error handling and verification
        """
        if total_bandwidth_mbps is None:
            total_bandwidth_mbps = getattr(Config, "TOTAL_BANDWIDTH_MBPS", 100)
        
        try:
            logger.info(f"🔧 Initializing TC on interface: {self.interface}")
            
            # Step 1: Remove existing qdiscs (suppress errors if none exist)
            subprocess.run(
                f"tc qdisc del dev {self.interface} root 2>/dev/null",
                shell=True,
                timeout=5
            )
            logger.debug("✓ Cleaned existing TC rules")
            
            # Step 2: Add root HTB qdisc
            total_bw_kbit = total_bandwidth_mbps * 1000
            cmd = f"tc qdisc add dev {self.interface} root handle {self.root_handle} htb default 30"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                raise Exception(f"Failed to add root qdisc: {result.stderr}")
            logger.debug("✓ Added root HTB qdisc")
            
            # Step 3: Add root class with total bandwidth
            cmd = f"tc class add dev {self.interface} parent {self.root_handle} classid 1:1 htb rate {total_bw_kbit}kbit"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                raise Exception(f"Failed to add root class: {result.stderr}")
            logger.debug(f"✓ Added root class ({total_bandwidth_mbps} Mbps)")
            
            # Step 4: Create priority classes (1:10, 1:20, 1:30)
            priorities = {
                "1:10": int(total_bw_kbit * 0.5),  # High priority: 50%
                "1:20": int(total_bw_kbit * 0.3),  # Medium priority: 30%
                "1:30": int(total_bw_kbit * 0.2),  # Low priority: 20%
            }
            
            for classid, rate in priorities.items():
                cmd = f"tc class add dev {self.interface} parent 1:1 classid {classid} htb rate {rate}kbit ceil {total_bw_kbit}kbit"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                
                if result.returncode != 0:
                    raise Exception(f"Failed to add priority class {classid}: {result.stderr}")
                logger.debug(f"✓ Added priority class {classid} ({rate} kbit)")
            
            self.initialized = True
            logger.info(f"✅ TC initialized successfully on {self.interface} with {total_bandwidth_mbps} Mbps")
            
            # Verify initialization
            self._verify_tc_setup()
            
        except subprocess.TimeoutExpired:
            logger.error("❌ TC command timed out - check system load")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to initialize TC: {e}")
            logger.info("Troubleshooting:")
            logger.info("1. Check if running with sudo: sudo python app.py")
            logger.info("2. Verify interface exists: ip link show")
            logger.info("3. Check kernel modules: lsmod | grep sch_htb")
            raise
    
    def _verify_tc_setup(self):
        """Verify TC was set up correctly"""
        try:
            result = subprocess.run(
                f"tc qdisc show dev {self.interface}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            if "htb" in result.stdout:
                logger.debug("✓ TC setup verified (HTB found)")
            else:
                logger.warning("⚠ TC setup may be incomplete")
        except Exception as e:
            logger.warning(f"Could not verify TC setup: {e}")
    
    def _get_classid_for_priority(self, priority: int) -> str:
        """Map priority level to TC class ID"""
        priority_map = {
            1: "1:10",  # High
            2: "1:20",  # Medium
            3: "1:30",  # Low
        }
        return priority_map.get(priority, "1:30")
    
    def apply_allocation(self, allocation: BandwidthAllocation):
        """
        Apply bandwidth allocation for a specific MAC address
        FIXED: Better error handling and validation
        """
        if not self.initialized:
            logger.warning("⚠ TC not initialized. Initializing with defaults...")
            try:
                self.initialize_qdisc()
            except Exception as e:
                logger.error(f"❌ Cannot initialize TC: {e}")
                return
        
        mac = allocation.mac_address.lower()
        bw_kbps = allocation.allocated_bw_kbps
        priority = allocation.priority
        
        # Validate inputs
        if bw_kbps <= 0:
            logger.error(f"❌ Invalid bandwidth for {mac}: {bw_kbps} kbps")
            return
        
        if priority not in [1, 2, 3]:
            logger.error(f"❌ Invalid priority for {mac}: {priority}")
            return
        
        try:
            # Generate unique handle for this MAC
            mac_hash = abs(hash(mac)) % 10000
            handle = f"1:{100 + mac_hash}"
            parent_class = self._get_classid_for_priority(priority)
            
            # Remove existing class for this MAC if exists
            if mac in self.active_allocations:
                old_handle = f"1:{100 + abs(hash(mac)) % 10000}"
                
                # Delete old filters
                subprocess.run(
                    f"tc filter del dev {self.interface} parent {self.root_handle} prio {priority} 2>/dev/null",
                    shell=True,
                    timeout=5
                )
                
                # Delete old class
                subprocess.run(
                    f"tc class del dev {self.interface} classid {old_handle} 2>/dev/null",
                    shell=True,
                    timeout=5
                )
                logger.debug(f"✓ Removed old allocation for {mac}")
            
            # Add class for this device with allocated bandwidth
            ceil_bw = min(bw_kbps * 2, 100000)  # Ceil at 2x rate or 100 Mbps
            cmd = f"tc class add dev {self.interface} parent {parent_class} classid {handle} htb rate {bw_kbps}kbit ceil {ceil_bw}kbit"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                raise Exception(f"Failed to add class: {result.stderr}")
            logger.debug(f"✓ Added class {handle} for {mac}")
            
            # Add filter to match MAC address for upload (src MAC)
            cmd_up = f"tc filter add dev {self.interface} protocol ip parent {self.root_handle} prio {priority} u32 match ether src {mac} flowid {handle}"
            result = subprocess.run(cmd_up, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                logger.warning(f"⚠ Upload filter failed for {mac}: {result.stderr}")
            else:
                logger.debug(f"✓ Added upload filter for {mac}")
            
            # Add filter for download (dst MAC)
            cmd_down = f"tc filter add dev {self.interface} protocol ip parent {self.root_handle} prio {priority} u32 match ether dst {mac} flowid {handle}"
            result = subprocess.run(cmd_down, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                logger.warning(f"⚠ Download filter failed for {mac}: {result.stderr}")
            else:
                logger.debug(f"✓ Added download filter for {mac}")
            
            # Store allocation
            self.active_allocations[mac] = allocation
            logger.info(f"✅ Applied {bw_kbps} kbps (priority {priority}) to MAC {mac}")
            
        except subprocess.TimeoutExpired:
            logger.error(f"❌ TC command timed out for {mac}")
        except Exception as e:
            logger.error(f"❌ Failed to apply allocation for {mac}: {e}")
    
    def remove_allocation(self, mac_address: str):
        """Remove bandwidth allocation for a MAC address"""
        mac = mac_address.lower()
        
        if mac not in self.active_allocations:
            logger.warning(f"⚠ No active allocation for {mac}")
            return
        
        try:
            mac_hash = abs(hash(mac)) % 10000
            handle = f"1:{100 + mac_hash}"
            priority = self.active_allocations[mac].priority
            
            # Remove filters
            subprocess.run(
                f"tc filter del dev {self.interface} parent {self.root_handle} prio {priority} 2>/dev/null",
                shell=True,
                timeout=5
            )
            
            # Remove class
            subprocess.run(
                f"tc class del dev {self.interface} classid {handle} 2>/dev/null",
                shell=True,
                timeout=5
            )
            
            del self.active_allocations[mac]
            logger.info(f"✓ Removed allocation for {mac}")
            
        except Exception as e:
            logger.error(f"❌ Failed to remove allocation for {mac}: {e}")
    
    def get_stats(self) -> Dict:
        """Get current TC statistics"""
        try:
            result = subprocess.run(
                f"tc -s class show dev {self.interface}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            return {"raw_stats": result.stdout, "success": result.returncode == 0}
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"raw_stats": "", "success": False, "error": str(e)}
    
    def cleanup(self):
        """Remove all TC configurations"""
        try:
            subprocess.run(
                f"tc qdisc del dev {self.interface} root 2>/dev/null",
                shell=True,
                timeout=5
            )
            self.active_allocations.clear()
            self.initialized = False
            logger.info(f"✓ Cleaned up TC on {self.interface}")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


class BandwidthDecisionEngine:
    """
    Decision engine that takes ML predictions and enforces bandwidth allocations
    """
    
    def __init__(self, 
                 interface: str = "ap1-wlan1",
                 update_interval: int = 10,
                 change_threshold: float = 0.15):
        """
        Args:
            interface: Network interface for TC
            update_interval: Seconds between enforcement cycles
            change_threshold: Minimum fractional change to trigger update (0.15 = 15%)
        """
        self.tc_controller = TrafficController(interface)
        self.update_interval = update_interval
        self.change_threshold = change_threshold
        self.ap_mac = None  # Will be detected at runtime
        
        # Try to initialize TC at startup
        try:
            self.tc_controller.initialize_qdisc()
        except Exception as e:
            logger.error(f"❌ Failed to initialize TC at startup: {e}")
            logger.warning("⚠ Bandwidth enforcement will not work until TC is initialized")
    
    def detect_ap_mac(self) -> Optional[str]:
        """Detect AP's MAC address from interface"""
        try:
            result = subprocess.run(
                f"ip link show {self.tc_controller.interface}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            # Parse MAC from output like "link/ether aa:bb:cc:dd:ee:ff"
            for line in result.stdout.split('\n'):
                if 'link/ether' in line:
                    mac = line.split()[1]
                    self.ap_mac = mac.lower()
                    logger.info(f"✓ Detected AP MAC: {self.ap_mac}")
                    return self.ap_mac
        except Exception as e:
            logger.error(f"Failed to detect AP MAC: {e}")
        return None
    
    def should_update(self, 
                     old_allocation: Optional[BandwidthAllocation],
                     new_allocation: BandwidthAllocation) -> bool:
        """Determine if allocation should be updated based on threshold"""
        if old_allocation is None:
            return True  # New device
        
        old_bw = old_allocation.allocated_bw_kbps
        new_bw = new_allocation.allocated_bw_kbps
        
        # Calculate fractional change
        change = abs(new_bw - old_bw) / old_bw if old_bw > 0 else 1.0
        
        # Update if change exceeds threshold or priority changed
        return (change >= self.change_threshold or 
                old_allocation.priority != new_allocation.priority)
    
    def process_ml_predictions(self, predictions: List[Dict]):
        """Process ML model predictions and enforce bandwidth allocations"""
        if self.ap_mac is None:
            self.detect_ap_mac()
        
        allocations_to_apply = []
        
        for pred in predictions:
            mac = pred['mac_address'].lower()
            
            # Skip AP's own MAC address
            if self.ap_mac and mac == self.ap_mac:
                logger.debug(f"Skipping AP MAC: {mac}")
                continue
            
            # Determine priority based on traffic class
            priority = self._classify_priority(
                pred.get('traffic_class', 'unknown'),
                pred.get('is_anomaly', False)
            )
            
            # Cap bandwidth if anomaly detected
            predicted_bw = pred['predicted_bandwidth_kbps']
            if pred.get('is_anomaly', False):
                cap = getattr(Config, 'ANOMALY_BANDWIDTH_CAP', 1000)
                predicted_bw = min(predicted_bw, cap)
                logger.warning(f"⚠ Anomaly detected for {mac}, capping bandwidth to {cap} kbps")
            
            # Create allocation
            allocation = BandwidthAllocation(
                mac_address=mac,
                allocated_bw_kbps=predicted_bw,
                priority=priority,
                device_ip=pred.get('ip_address')
            )
            
            # Check if update is needed
            old_allocation = self.tc_controller.active_allocations.get(mac)
            if self.should_update(old_allocation, allocation):
                allocations_to_apply.append(allocation)
        
        # Apply all allocations
        for allocation in allocations_to_apply:
            self.tc_controller.apply_allocation(allocation)
        
        logger.info(f"✓ Processed {len(predictions)} predictions, applied {len(allocations_to_apply)} updates")
    
    def _classify_priority(self, traffic_class: str, is_anomaly: bool) -> int:
        """Map traffic class to priority level"""
        if is_anomaly:
            return 3  # Lowest priority for anomalies
        
        priority_map = {
            'voip': 1,
            'video_conference': 1,
            'video': 1,
            'streaming': 2,
            'web': 2,
            'bulk': 3,
            'file_transfer': 3,
            'unknown': 2,
        }
        return priority_map.get(traffic_class.lower(), 2)
    
    def run_enforcement_loop(self, get_predictions_fn):
        """Main enforcement loop - calls ML prediction function periodically"""
        # Initialize TC
        try:
            self.tc_controller.initialize_qdisc(
                total_bandwidth_mbps=getattr(Config, 'TOTAL_BANDWIDTH_MBPS', 100)
            )
        except Exception as e:
            logger.error(f"❌ Cannot start enforcement loop: TC initialization failed")
            return
        
        logger.info(f"▶️ Starting enforcement loop (interval: {self.update_interval}s)")
        
        try:
            while True:
                try:
                    # Get predictions from ML models
                    predictions = get_predictions_fn()
                    
                    if predictions:
                        self.process_ml_predictions(predictions)
                    else:
                        logger.debug("No predictions received")
                    
                    # Wait for next cycle
                    time.sleep(self.update_interval)
                    
                except Exception as e:
                    logger.error(f"Error in enforcement loop: {e}")
                    time.sleep(self.update_interval)
        
        except KeyboardInterrupt:
            logger.info("Enforcement loop stopped by user")
            self.tc_controller.cleanup()


# Example usage
if __name__ == "__main__":
    def mock_get_predictions():
        """Mock function simulating ML predictions"""
        return [
            {
                'mac_address': '00:11:22:33:44:55',
                'predicted_bandwidth_kbps': 5000,
                'traffic_class': 'video_conference',
                'is_anomaly': False,
                'ip_address': '10.0.0.2'
            }
        ]
    
    # Create decision engine
    engine = BandwidthDecisionEngine(
        interface="ap1-wlan1",
        update_interval=10,
        change_threshold=0.15
    )
    
    # Run enforcement loop
    engine.run_enforcement_loop(mock_get_predictions)