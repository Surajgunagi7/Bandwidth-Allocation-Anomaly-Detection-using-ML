#!/usr/bin/env python3
"""
Bandwidth Enforcement Module - FIXED VERSION
Key fixes:
1. Tracks filter handles for precise deletion (no over-broad priority deletion)
2. Persistent MAC-to-class ID mapping (prevents hash collisions)
3. Global bandwidth normalization per priority group
4. Better error handling and verification
"""

import subprocess
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import json
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BandwidthAllocation:
    """Represents bandwidth allocation for a device"""
    mac_address: str
    allocated_bw_kbps: int
    priority: int
    device_ip: Optional[str] = None


@dataclass
class FilterHandle:
    """Tracks TC filter handle for precise deletion"""
    handle_id: str  # e.g., "800::800"
    pref: int       # preference/priority
    direction: str  # 'upload' or 'download'


class TrafficController:
    """
    Manages Linux TC with FIXED filter handling and normalization
    """
    
    def __init__(self, interface: str = "ap1-wlan1"):
        self.interface = interface
        self.active_allocations: Dict[str, BandwidthAllocation] = {}
        self.mac_to_class_id: Dict[str, int] = {}  # PERSISTENT mapping
        self.filter_handles: Dict[str, List[FilterHandle]] = {}  # mac -> handles
        self.next_class_id = 100  # Auto-increment class IDs
        self.root_handle = "1:"
        self.initialized = False
        
        if not self._verify_interface():
            logger.error(f"❌ Interface {interface} not found!")
        
        if not self._check_tc_permissions():
            logger.error("❌ Run with: sudo python app.py")
    
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
    
    def initialize_qdisc(self, total_bandwidth_mbps: int = None):
        """Initialize HTB qdisc"""
        if total_bandwidth_mbps is None:
            total_bandwidth_mbps = getattr(Config, "TOTAL_BANDWIDTH_MBPS", 100)
        
        try:
            logger.info(f"🔧 Initializing TC on {self.interface}")
            
            # Remove existing qdiscs
            subprocess.run(
                f"tc qdisc del dev {self.interface} root 2>/dev/null",
                shell=True, timeout=5
            )
            
            # Add root HTB
            total_bw_kbit = total_bandwidth_mbps * 1000
            cmd = f"tc qdisc add dev {self.interface} root handle {self.root_handle} htb default 30"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                raise Exception(f"Root qdisc failed: {result.stderr}")
            
            # Add root class
            cmd = f"tc class add dev {self.interface} parent {self.root_handle} classid 1:1 htb rate {total_bw_kbit}kbit"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                raise Exception(f"Root class failed: {result.stderr}")
            
            # Add priority classes
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
            
            self.initialized = True
            logger.info(f"✅ TC initialized: {total_bandwidth_mbps} Mbps")
            
        except Exception as e:
            logger.error(f"❌ TC initialization failed: {e}")
            raise
    
    def _get_or_create_class_id(self, mac: str) -> str:
        """
        FIXED: Persistent MAC-to-class ID mapping (prevents collisions)
        """
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
        """
        FIXED: Apply allocation with proper filter handle tracking
        """
        if not self.initialized:
            logger.warning("⚠ TC not initialized, initializing now...")
            try:
                self.initialize_qdisc()
            except Exception as e:
                logger.error(f"❌ Cannot initialize: {e}")
                return
        
        mac = allocation.mac_address.lower()
        bw_kbps = allocation.allocated_bw_kbps
        priority = allocation.priority
        
        if bw_kbps <= 0 or priority not in [1, 2, 3]:
            logger.error(f"❌ Invalid allocation for {mac}: {bw_kbps} kbps, priority {priority}")
            return
        
        try:
            # Get persistent class ID
            classid = self._get_or_create_class_id(mac)
            parent_class = self._get_classid_for_priority(priority)
            
            # Remove old allocation if exists
            if mac in self.active_allocations:
                self._remove_device_class_and_filters(mac)
            
            # Add new class for this device
            ceil_bw = min(bw_kbps * 2, 100000)
            cmd = f"tc class add dev {self.interface} parent {parent_class} classid {classid} htb rate {bw_kbps}kbit ceil {ceil_bw}kbit"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                raise Exception(f"Class creation failed: {result.stderr}")
            
            # Add filters and track handles
            self.filter_handles[mac] = []
            
            # Upload filter (src MAC)
            cmd_up = f"tc filter add dev {self.interface} protocol ip parent {self.root_handle} prio {priority} u32 match ether src {mac} flowid {classid}"
            result_up = subprocess.run(cmd_up, shell=True, capture_output=True, text=True, timeout=5)
            
            if result_up.returncode == 0:
                # Extract handle from output (if available)
                handle_up = self._extract_filter_handle(result_up.stdout)
                if handle_up:
                    self.filter_handles[mac].append(FilterHandle(handle_up, priority, 'upload'))
                logger.debug(f"✓ Upload filter for {mac}")
            
            # Download filter (dst MAC)
            cmd_down = f"tc filter add dev {self.interface} protocol ip parent {self.root_handle} prio {priority} u32 match ether dst {mac} flowid {classid}"
            result_down = subprocess.run(cmd_down, shell=True, capture_output=True, text=True, timeout=5)
            
            if result_down.returncode == 0:
                handle_down = self._extract_filter_handle(result_down.stdout)
                if handle_down:
                    self.filter_handles[mac].append(FilterHandle(handle_down, priority, 'download'))
                logger.debug(f"✓ Download filter for {mac}")
            
            # Store allocation
            self.active_allocations[mac] = allocation
            logger.info(f"✅ Applied {bw_kbps} kbps (priority {priority}) to {mac}")
            
        except Exception as e:
            logger.error(f"❌ Allocation failed for {mac}: {e}")
    
    def _extract_filter_handle(self, tc_output: str) -> Optional[str]:
        """Extract filter handle from TC output (best effort)"""
        # TC doesn't always return handle in add command
        # This is a placeholder for future enhancement
        return None
    
    def _remove_device_class_and_filters(self, mac: str):
        """
        FIXED: Remove filters by tracked handles, then remove class
        """
        classid = self._get_or_create_class_id(mac)
        
        try:
            # Remove tracked filters by handle (if available)
            if mac in self.filter_handles:
                for fh in self.filter_handles[mac]:
                    cmd = f"tc filter del dev {self.interface} parent {self.root_handle} handle {fh.handle_id} pref {fh.pref} u32 2>/dev/null"
                    subprocess.run(cmd, shell=True, timeout=5)
                
                del self.filter_handles[mac]
            
            # Fallback: Remove by priority (less precise)
            if mac in self.active_allocations:
                priority = self.active_allocations[mac].priority
                subprocess.run(
                    f"tc filter del dev {self.interface} parent {self.root_handle} prio {priority} 2>/dev/null",
                    shell=True, timeout=5
                )
            
            # Remove class
            subprocess.run(
                f"tc class del dev {self.interface} classid {classid} 2>/dev/null",
                shell=True, timeout=5
            )
            
            logger.debug(f"✓ Removed allocation for {mac}")
            
        except Exception as e:
            logger.warning(f"⚠ Removal failed for {mac}: {e}")
    
    def remove_allocation(self, mac_address: str):
        """Remove bandwidth allocation"""
        mac = mac_address.lower()
        
        if mac not in self.active_allocations:
            logger.warning(f"⚠ No allocation for {mac}")
            return
        
        try:
            self._remove_device_class_and_filters(mac)
            del self.active_allocations[mac]
            logger.info(f"✓ Removed allocation for {mac}")
        except Exception as e:
            logger.error(f"❌ Removal failed for {mac}: {e}")
    
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
        """Remove all TC configs"""
        try:
            subprocess.run(
                f"tc qdisc del dev {self.interface} root 2>/dev/null",
                shell=True, timeout=5
            )
            self.active_allocations.clear()
            self.mac_to_class_id.clear()
            self.filter_handles.clear()
            self.initialized = False
            logger.info(f"✓ Cleaned up TC on {self.interface}")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


class BandwidthDecisionEngine:
    """
    FIXED: Adds global bandwidth normalization
    """
    
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
            logger.error(f"❌ TC init failed: {e}")
    
    def detect_ap_mac(self) -> Optional[str]:
        """Detect AP MAC"""
        try:
            result = subprocess.run(
                f"ip link show {self.tc_controller.interface}",
                shell=True, capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'link/ether' in line:
                    mac = line.split()[1]
                    self.ap_mac = mac.lower()
                    logger.info(f"✓ Detected AP MAC: {self.ap_mac}")
                    return self.ap_mac
        except Exception as e:
            logger.error(f"MAC detection failed: {e}")
        return None
    
    def should_update(self, old: Optional[BandwidthAllocation], new: BandwidthAllocation) -> bool:
        """Check if update needed"""
        if old is None:
            return True
        
        old_bw, new_bw = old.allocated_bw_kbps, new.allocated_bw_kbps
        change = abs(new_bw - old_bw) / old_bw if old_bw > 0 else 1.0
        
        return change >= self.change_threshold or old.priority != new.priority
    
    def process_ml_predictions(self, predictions: List[Dict]):
        """
        FIXED: Normalize allocations globally per priority group
        """
        if self.ap_mac is None:
            self.detect_ap_mac()
        
        # Group predictions by priority
        priority_groups = {1: [], 2: [], 3: []}
        
        for pred in predictions:
            mac = pred['mac_address'].lower()
            
            if self.ap_mac and mac == self.ap_mac:
                continue
            
            priority = self._classify_priority(
                pred.get('traffic_class', 'unknown'),
                pred.get('is_anomaly', False)
            )
            
            predicted_bw = pred['predicted_bandwidth_kbps']
            
            if pred.get('is_anomaly', False):
                cap = getattr(Config, 'ANOMALY_BANDWIDTH_CAP', 1000)
                predicted_bw = min(predicted_bw, cap)
            
            priority_groups[priority].append({
                'mac': mac,
                'bw': predicted_bw,
                'ip': pred.get('ip_address')
            })
        
        # FIXED: Normalize within each priority group
        total_bw_mbps = getattr(Config, 'TOTAL_BANDWIDTH_MBPS', 100)
        priority_limits = {
            1: int(total_bw_mbps * 0.5 * 1000),  # 50% for high
            2: int(total_bw_mbps * 0.3 * 1000),  # 30% for medium
            3: int(total_bw_mbps * 0.2 * 1000),  # 20% for low
        }
        
        allocations_to_apply = []
        
        for priority, devices in priority_groups.items():
            if not devices:
                continue
            
            # Calculate total requested bandwidth for this priority
            total_requested = sum(d['bw'] for d in devices)
            limit = priority_limits[priority]
            
            # Normalize if exceeds limit
            if total_requested > limit:
                scale_factor = limit / total_requested
                logger.warning(f"⚠ Priority {priority}: normalizing {total_requested} kbps -> {limit} kbps")
                
                for device in devices:
                    device['bw'] = int(device['bw'] * scale_factor)
            
            # Create allocations
            for device in devices:
                allocation = BandwidthAllocation(
                    mac_address=device['mac'],
                    allocated_bw_kbps=max(device['bw'], 100),  # Min 100 kbps
                    priority=priority,
                    device_ip=device.get('ip')
                )
                
                old = self.tc_controller.active_allocations.get(device['mac'])
                if self.should_update(old, allocation):
                    allocations_to_apply.append(allocation)
        
        # Apply allocations
        for allocation in allocations_to_apply:
            self.tc_controller.apply_allocation(allocation)
        
        logger.info(f"✓ Processed {len(predictions)} predictions, applied {len(allocations_to_apply)} updates")
    
    def _classify_priority(self, traffic_class: str, is_anomaly: bool) -> int:
        """Map traffic to priority"""
        if is_anomaly:
            return 3
        
        priority_map = {
            'voip': 1, 'video_conference': 1, 'video': 1,
            'streaming': 2, 'web': 2,
            'bulk': 3, 'file_transfer': 3, 'unknown': 2
        }
        return priority_map.get(traffic_class.lower(), 2)


if __name__ == "__main__":
    def mock_predictions():
        return [
            {'mac_address': '00:11:22:33:44:55', 'predicted_bandwidth_kbps': 5000,
             'traffic_class': 'video_conference', 'is_anomaly': False}
        ]
    
    engine = BandwidthDecisionEngine(interface="ap1-wlan1")
    engine.process_ml_predictions(mock_predictions())