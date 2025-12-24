#!/usr/bin/env python3
"""
Bandwidth Enforcement Module - FULLY FIXED
Key fixes:
1. Complete TC cleanup before initialization
2. Robust MAC-to-class ID management with collision prevention
3. Proper filter deletion using prio parameter
4. Better bandwidth normalization with minimums
5. Improved error handling and logging
"""

import subprocess
import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class BandwidthAllocation:
    """Represents bandwidth allocation for a device"""
    mac_address: str
    allocated_bw_kbps: int
    priority: int
    device_ip: Optional[str] = None


class TrafficController:
    """Manages Linux TC with robust class and filter handling"""
    
    def __init__(self, interface: str = "ap1-wlan1"):
        self.interface = interface
        self.active_allocations: Dict[str, BandwidthAllocation] = {}
        self.mac_to_class_id: Dict[str, int] = {}
        self.next_class_id = 100
        self.root_handle = "1:"
        self.initialized = False
        
        if not self._verify_interface():
            logger.error(f"Interface {interface} not found!")
        
        if not self._check_tc_permissions():
            logger.error("Insufficient permissions - run with sudo")
    
    def _verify_interface(self) -> bool:
        """Verify interface exists"""
        try:
            result = subprocess.run(
                f"ip link show {self.interface}",
                shell=True, capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Interface verification failed: {e}")
            return False
    
    def _check_tc_permissions(self) -> bool:
        """Check TC permissions"""
        try:
            result = subprocess.run(
                "tc qdisc show", shell=True, capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _complete_cleanup(self):
        """THOROUGH cleanup of all TC configurations"""
        logger.info(f"Performing complete TC cleanup on {self.interface}")
        
        try:
            # Delete root qdisc (cascades to all classes and filters)
            subprocess.run(
                f"tc qdisc del dev {self.interface} root 2>/dev/null",
                shell=True, timeout=5
            )
            
            # Delete ingress qdisc if exists
            subprocess.run(
                f"tc qdisc del dev {self.interface} ingress 2>/dev/null",
                shell=True, timeout=5
            )
            
            # Brief pause to let kernel clean up
            time.sleep(0.2)
            
            # Clear internal state
            self.active_allocations.clear()
            self.mac_to_class_id.clear()
            self.next_class_id = 100
            self.initialized = False
            
            logger.info("TC cleanup complete")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def initialize_qdisc(self, total_bandwidth_mbps: int = None):
        """Initialize HTB qdisc with complete cleanup first"""
        if total_bandwidth_mbps is None:
            total_bandwidth_mbps = Config.get_total_bandwidth()
        
        try:
            logger.info(f"Initializing TC on {self.interface} with {total_bandwidth_mbps} Mbps")
            
            # COMPLETE cleanup first
            self._complete_cleanup()
            
            total_bw_kbit = total_bandwidth_mbps * 1000
            
            # Add root HTB qdisc
            cmd = f"tc qdisc add dev {self.interface} root handle {self.root_handle} htb default 30"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                raise Exception(f"Root qdisc failed: {result.stderr}")
            
            # Add root class (1:1)
            cmd = f"tc class add dev {self.interface} parent {self.root_handle} classid 1:1 htb rate {total_bw_kbit}kbit ceil {total_bw_kbit}kbit"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                raise Exception(f"Root class failed: {result.stderr}")
            
            # Add priority parent classes (1:10, 1:20, 1:30)
            priorities = {
                "1:10": int(total_bw_kbit * 0.5),  # High: 50%
                "1:20": int(total_bw_kbit * 0.3),  # Medium: 30%
                "1:30": int(total_bw_kbit * 0.2),  # Low: 20%
            }
            
            for classid, rate in priorities.items():
                cmd = f"tc class add dev {self.interface} parent 1:1 classid {classid} htb rate {rate}kbit ceil {total_bw_kbit}kbit"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    raise Exception(f"Priority class {classid} failed: {result.stderr}")
            
            # Add default leaf qdisc to catch unmatched traffic
            cmd = f"tc qdisc add dev {self.interface} parent 1:30 handle 30: sfq"
            subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            
            self.initialized = True
            logger.info(f"TC initialized successfully: {total_bandwidth_mbps} Mbps")
            
        except Exception as e:
            logger.error(f"TC initialization failed: {e}")
            self.initialized = False
            raise
    
    def _get_or_create_class_id(self, mac: str) -> str:
        """Persistent MAC-to-class ID mapping"""
        if mac not in self.mac_to_class_id:
            self.mac_to_class_id[mac] = self.next_class_id
            self.next_class_id += 1
        
        class_id = self.mac_to_class_id[mac]
        return f"1:{class_id}"
    
    def _get_classid_for_priority(self, priority: int) -> str:
        """Map priority to parent class"""
        priority_map = {1: "1:10", 2: "1:20", 3: "1:30"}
        return priority_map.get(priority, "1:30")
    
    def apply_allocation(self, allocation: BandwidthAllocation):
        """Apply bandwidth allocation with proper conflict resolution"""
        if not self.initialized:
            logger.warning("TC not initialized, initializing now...")
            try:
                self.initialize_qdisc()
            except Exception as e:
                logger.error(f"Cannot initialize: {e}")
                return
        
        mac = allocation.mac_address.lower()
        bw_kbps = max(allocation.allocated_bw_kbps, Config.MIN_BANDWIDTH_KBPS)
        priority = allocation.priority
        
        if priority not in [1, 2, 3]:
            logger.error(f"Invalid priority {priority} for {mac}")
            return
        
        try:
            # Get persistent class ID
            classid = self._get_or_create_class_id(mac)
            parent_class = self._get_classid_for_priority(priority)
            
            # Remove old allocation if exists
            if mac in self.active_allocations:
                self._remove_device_allocation(mac)
            
            # Create new class for this device
            check = subprocess.run(
                f"tc class show dev {self.interface} | grep {parent_class}",
                shell=True, capture_output=True
            )
            if check.returncode != 0:
                logger.warning("Parent class missing, reinitializing TC")
                self.initialize_qdisc()
                return
            
            ceil_bw = min(bw_kbps * 2, Config.get_total_bandwidth() * 1000)
            cmd = f"tc class add dev {self.interface} parent {parent_class} classid {classid} htb rate {bw_kbps}kbit ceil {ceil_bw}kbit"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                if "File exists" in result.stderr:
                    # Class exists - delete and retry
                    logger.warning(f"Class {classid} exists, removing and retrying")
                    subprocess.run(
                        f"tc class del dev {self.interface} classid {classid} 2>/dev/null",
                        shell=True, timeout=5
                    )
                    time.sleep(0.1)
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                    if result.returncode != 0:
                        raise Exception(f"Class creation retry failed: {result.stderr}")
                else:
                    raise Exception(f"Class creation failed: {result.stderr}")
            
            # Add leaf qdisc
            subprocess.run(
                f"tc qdisc add dev {self.interface} parent {classid} handle {classid.split(':')[1]}: sfq 2>/dev/null",
                shell=True, timeout=5
            )
            
            # Add filters (upload and download)
            # Upload filter (source MAC)
            cmd_up = f"tc filter add dev {self.interface} protocol all parent {self.root_handle} prio {priority} u32 match ether src {mac} flowid {classid}"
            result_up = subprocess.run(cmd_up, shell=True, capture_output=True, text=True, timeout=5)
            
            if result_up.returncode != 0:
                logger.debug(f"Upload filter warning for {mac}: {result_up.stderr}")
            
            # Download filter (destination MAC)
            cmd_down = f"tc filter add dev {self.interface} protocol all parent {self.root_handle} prio {priority} u32 match ether dst {mac} flowid {classid}"
            result_down = subprocess.run(cmd_down, shell=True, capture_output=True, text=True, timeout=5)
            
            if result_down.returncode != 0:
                logger.debug(f"Download filter warning for {mac}: {result_down.stderr}")
            
            # Store allocation
            self.active_allocations[mac] = allocation
            logger.info(f"✅ Applied {bw_kbps} kbps (priority {priority}) to {mac}")
            
        except Exception as e:
            logger.error(f"Allocation failed for {mac}: {e}")
    
    def _remove_device_allocation(self, mac: str):
        """Remove device's allocation (class and filters)"""
        if mac not in self.active_allocations:
            return
        
        try:
            class_num = self.mac_to_class_id.get(mac)
            if class_num is None:
                return

            classid = f"1:{class_num}"

            priority = self.active_allocations[mac].priority
            
            # Delete filters by priority
            subprocess.run(
                f"tc filter del dev {self.interface} parent {self.root_handle} prio {priority} 2>/dev/null",
                shell=True, timeout=5
            )
            
            # Delete leaf qdisc if exists
            handle_id = classid.split(':')[1]
            subprocess.run(
                f"tc qdisc del dev {self.interface} handle {handle_id}: 2>/dev/null",
                shell=True, timeout=5
            )
            
            # Delete class
            subprocess.run(
                f"tc class del dev {self.interface} classid {classid} 2>/dev/null",
                shell=True, timeout=5
            )
            
            logger.debug(f"Removed allocation for {mac}")
            
        except Exception as e:
            logger.warning(f"Removal warning for {mac}: {e}")
    
    def remove_allocation(self, mac_address: str):
        """Public method to remove allocation"""
        mac = mac_address.lower()
        
        if mac not in self.active_allocations:
            logger.warning(f"No allocation found for {mac}")
            return
        
        try:
            self._remove_device_allocation(mac)
            del self.active_allocations[mac]
            logger.info(f"✅ Removed allocation for {mac}")
        except Exception as e:
            logger.error(f"Removal failed for {mac}: {e}")
    
    def get_stats(self) -> Dict:
        """Get TC statistics"""
        try:
            result = subprocess.run(
                f"tc -s class show dev {self.interface}",
                shell=True, capture_output=True, text=True, timeout=5
            )
            return {"raw_stats": result.stdout, "success": result.returncode == 0}
        except Exception as e:
            return {"raw_stats": "", "success": False, "error": str(e)}
    
    def cleanup(self):
        """Complete cleanup"""
        self._complete_cleanup()


class BandwidthDecisionEngine:
    """Decision engine with improved bandwidth distribution"""
    
    def __init__(self, interface: str = "ap1-wlan1",
                 update_interval: int = 10,
                 change_threshold: float = 0.15):
        self.tc_controller = TrafficController(interface)
        self.update_interval = update_interval
        self.change_threshold = change_threshold
        self.ap_mac = None
        
        try:
            self.tc_controller.initialize_qdisc()
        except Exception as e:
            logger.error(f"TC init failed: {e}")
    
    def detect_ap_mac(self) -> Optional[str]:
        """Detect AP MAC address"""
        try:
            result = subprocess.run(
                f"ip link show {self.tc_controller.interface}",
                shell=True, capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'link/ether' in line:
                    mac = line.split()[1]
                    self.ap_mac = mac.lower()
                    Config.KNOWN_AP_MACS.add(self.ap_mac)
                    logger.info(f"Detected AP MAC: {self.ap_mac}")
                    return self.ap_mac
        except Exception as e:
            logger.error(f"MAC detection failed: {e}")
        return None
    
    def should_update(self, old: Optional[BandwidthAllocation], new: BandwidthAllocation) -> bool:
        """Check if update is needed"""
        if old is None:
            return True
        
        old_bw, new_bw = old.allocated_bw_kbps, new.allocated_bw_kbps
        change = abs(new_bw - old_bw) / old_bw if old_bw > 0 else 1.0
        
        return change >= self.change_threshold or old.priority != new.priority
    
    def process_ml_predictions(self, predictions: List[Dict]):
        """Process ML predictions with improved normalization"""

        if Config.NO_BANDWIDTH_LIMIT_MODE:
            logger.info("Skipping TC enforcement (NO_BANDWIDTH_LIMIT_MODE)")
            return
        
        if self.ap_mac is None:
            self.detect_ap_mac()
        
        # Group by priority
        priority_groups = {1: [], 2: [], 3: []}
        
        for pred in predictions:
            mac = pred['mac_address'].lower()
            
            # Skip AP MAC
            if self.ap_mac and mac == self.ap_mac:
                continue
            
            priority = self._classify_priority(
                pred.get('traffic_class', 'unknown'),
                pred.get('is_anomaly', False)
            )
            
            predicted_bw = pred['predicted_bandwidth_kbps']
            
            # Cap anomalies
            if pred.get('is_anomaly', False):
                cap = Config.ANOMALY_BANDWIDTH_CAP
                predicted_bw = min(predicted_bw, cap)
            
            # Ensure minimum
            predicted_bw = max(predicted_bw, Config.MIN_BANDWIDTH_KBPS)
            
            priority_groups[priority].append({
                'mac': mac,
                'bw': predicted_bw,
                'ip': pred.get('ip_address')
            })
        
        # Normalize per priority group
        total_bw_mbps = Config.get_total_bandwidth()
        priority_limits = {
            1: int(total_bw_mbps * 0.5 * 1000),  # 50%
            2: int(total_bw_mbps * 0.3 * 1000),  # 30%
            3: int(total_bw_mbps * 0.2 * 1000),  # 20%
        }
        
        allocations_to_apply = []
        
        for priority, devices in priority_groups.items():
            if not devices:
                continue
            
            total_requested = sum(d['bw'] for d in devices)
            limit = priority_limits[priority]
            
            # Normalize if exceeds
            if total_requested > limit:
                scale_factor = limit / total_requested
                logger.info(f"Priority {priority}: normalizing {total_requested} kbps -> {limit} kbps")
                
                for device in devices:
                    device['bw'] = max(int(device['bw'] * scale_factor), Config.MIN_BANDWIDTH_KBPS)
            
            # Create allocations
            for device in devices:
                allocation = BandwidthAllocation(
                    mac_address=device['mac'],
                    allocated_bw_kbps=device['bw'],
                    priority=priority,
                    device_ip=device.get('ip')
                )
                
                old = self.tc_controller.active_allocations.get(device['mac'])
                if old and old.priority == allocation.priority and not self.should_update(old, allocation):
                    continue
                allocations_to_apply.append(allocation)
        
        # Apply allocations
        for allocation in allocations_to_apply:
            self.tc_controller.apply_allocation(allocation)
        
        logger.info(f"Processed {len(predictions)} predictions, applied {len(allocations_to_apply)} updates")
    
    def _classify_priority(self, traffic_class: str, is_anomaly: bool) -> int:
        """Map traffic to priority"""
        if is_anomaly:
            return 3
        
        return Config.TRAFFIC_CLASS_MAP.get(traffic_class.lower(), 2)


if __name__ == "__main__":
    def mock_predictions():
        return [
            {
                'mac_address': '00:11:22:33:44:55', 
                'predicted_bandwidth_kbps': 5000,
                'traffic_class': 'video', 
                'is_anomaly': False
            }
        ]
    
    engine = BandwidthDecisionEngine(interface="ap1-wlan1")
    engine.process_ml_predictions(mock_predictions())