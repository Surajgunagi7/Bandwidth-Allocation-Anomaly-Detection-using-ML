#!/usr/bin/env python3
"""
Dataset Generation Script for Training ML Models
Automates Mininet-WiFi simulations and data collection
"""

import os
import time
import subprocess
import json
import shutil
import signal
from pathlib import Path
from datetime import datetime
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MininetwifiScenarioGenerator:
    """Generate training data through Mininet-WiFi simulations"""
    
    def __init__(self, 
                 output_dir: str = "./training_data",
                 pcap_dir: str = "./training_data/pcap_captures"):
        """
        Args:
            output_dir: Directory to save processed features
            pcap_dir: Directory to save raw PCAP files
        """
        self.output_dir = Path(output_dir)
        self.pcap_dir = Path(pcap_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.pcap_dir.mkdir(exist_ok=True, parents=True)
        
        # Make pcap_dir accessible to collector
        self.pcap_dir.chmod(0o777)
        
        self.scenarios = []
        self._define_scenarios()
    
    def _define_scenarios(self):
        """Define all simulation scenarios with labels"""
        
        # Normal Traffic Scenarios
        self.scenarios.extend([
            {
                'name': 'light_browsing',
                'label': 'normal',
                'bandwidth_label': 'low',
                'bandwidth_kbps': 500,
                'command': 'ping -c 30 -i 1 {server}',
                'duration': 35,
                'repeat': 2  # Start with 2 for testing
            },
            {
                'name': 'video_streaming',
                'label': 'normal',
                'bandwidth_label': 'medium',
                'bandwidth_kbps': 3000,
                'command': 'iperf3 -c {server} -u -b 3M -t 30',
                'duration': 35,
                'repeat': 2,
                'requires_iperf': True
            },
            {
                'name': 'voip_call',
                'label': 'normal',
                'bandwidth_label': 'low',
                'bandwidth_kbps': 128,
                'command': 'iperf3 -c {server} -u -b 128K -t 30',
                'duration': 35,
                'repeat': 2,
                'requires_iperf': True
            },
            {
                'name': 'file_download',
                'label': 'normal',
                'bandwidth_label': 'high',
                'bandwidth_kbps': 8000,
                'command': 'iperf3 -c {server} -t 30',
                'duration': 35,
                'repeat': 2,
                'requires_iperf': True
            },
        ])
        
        # Anomaly Scenarios
        self.scenarios.extend([
            {
                'name': 'bandwidth_hog',
                'label': 'anomaly',
                'bandwidth_label': 'extreme',
                'bandwidth_kbps': 80000,
                'command': 'iperf3 -c {server} -P 10 -t 30',
                'duration': 35,
                'repeat': 2,
                'requires_iperf': True
            },
        ])
    
    def _create_custom_topology_script(self, scenario_name: str, pcap_output: str) -> str:
        """Create a custom topology script that captures to specific PCAP file"""
        
        # Read the original topology
        original_topo = Path(__file__).parent.parent / "mininet" / "topology.py"
        if not original_topo.exists():
            raise FileNotFoundError(f"topology.py not found at {original_topo}")
        
        # Create temporary modified topology
        temp_script = Path(f"/tmp/topology_{scenario_name}.py")
        
        with open(original_topo, 'r') as f:
            content = f.read()
        
        # Modify to use specific PCAP output path
        modified_content = content.replace(
            'PCAP_FILE = "/tmp/traffic.pcap"',
            f'PCAP_FILE = "{pcap_output}"'
        )
        
        with open(temp_script, 'w') as f:
            f.write(modified_content)
        
        return str(temp_script)
    
    def run_scenario(self, scenario: dict, iteration: int) -> str:
        """Run a single scenario iteration"""
        
        pcap_output = str(self.pcap_dir / f"{scenario['name']}_{iteration}.pcap")
        
        logger.info(f"Running {scenario['name']} (iter {iteration})")
        logger.info(f"PCAP will be saved to: {pcap_output}")
        
        # Clean up any previous Mininet processes
        subprocess.run("sudo mn -c 2>/dev/null", shell=True)
        subprocess.run("sudo pkill -9 -f 'tcpdump.*ap1'", shell=True)
        time.sleep(2)
        
        # Start tcpdump manually on the AP interface
        tcpdump_proc = None
        mininet_proc = None
        
        try:
            # Get original topology path
            original_topo = Path(__file__).parent.parent / "mininet" / "topology.py"
            
            # Start Mininet-WiFi in background
            logger.info("Starting Mininet-WiFi...")
            mininet_proc = subprocess.Popen(
                ["sudo", "python3", str(original_topo)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for network to initialize
            time.sleep(12)
            
            # Check if ap1-wlan1 interface exists
            check_if = subprocess.run(
                "ip link show ap1-wlan1",
                shell=True,
                capture_output=True,
                text=True
            )
            
            if check_if.returncode != 0:
                logger.error("ap1-wlan1 interface not found!")
                return ""
            
            logger.info("ap1-wlan1 interface found, starting tcpdump...")
            
            # Start tcpdump on ap1-wlan1
            tcpdump_proc = subprocess.Popen(
                f"sudo tcpdump -i ap1-wlan1 -w {pcap_output} -G 60 -W 1",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            time.sleep(2)
            
            # Get server IP (sta2 or h1, depending on topology)
            server_ip = "10.0.0.3"  # sta2's IP
            
            # For iperf scenarios, start server first
            if scenario.get('requires_iperf', False):
                logger.info("Starting iperf3 server on sta2...")
                subprocess.Popen(
                    f"sudo mnexec -a $(pgrep -f 'mininet:sta2') iperf3 -s -D",
                    shell=True
                )
                time.sleep(2)
            
            # Format command with server IP
            command = scenario['command'].replace('{server}', server_ip)
            
            # Execute traffic command on sta1
            logger.info(f"Executing command: {command}")
            
            # Try to get sta1's PID
            sta1_pid = subprocess.run(
                "pgrep -f 'mininet:sta1'",
                shell=True,
                capture_output=True,
                text=True
            ).stdout.strip()
            
            if sta1_pid:
                logger.info(f"Found sta1 PID: {sta1_pid}")
                exec_cmd = f"sudo mnexec -a {sta1_pid} {command}"
                subprocess.Popen(exec_cmd, shell=True)
            else:
                logger.warning("Could not find sta1 PID, using alternative method")
                # Alternative: use mn command
                subprocess.Popen(
                    f'echo "sta1 {command}" | sudo mn -x',
                    shell=True
                )
            
            # Wait for traffic to complete
            logger.info(f"Waiting {scenario['duration']}s for traffic to complete...")
            time.sleep(scenario['duration'])
            
        except Exception as e:
            logger.error(f"Error running scenario: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Stop tcpdump gracefully
            if tcpdump_proc:
                logger.info("Stopping tcpdump...")
                tcpdump_proc.send_signal(signal.SIGINT)
                time.sleep(2)
                tcpdump_proc.terminate()
            
            # Stop Mininet
            logger.info("Stopping Mininet...")
            if mininet_proc:
                mininet_proc.terminate()
            
            subprocess.run("sudo mn -c 2>/dev/null", shell=True)
            subprocess.run("sudo pkill -9 -f tcpdump", shell=True)
            time.sleep(3)
        
        # Check if PCAP was created
        if os.path.exists(pcap_output) and os.path.getsize(pcap_output) > 24:  # Valid PCAP header
            logger.info(f"✓ PCAP saved: {pcap_output} ({os.path.getsize(pcap_output)} bytes)")
            return pcap_output
        else:
            logger.warning(f"✗ PCAP not created or empty: {pcap_output}")
            return ""
    
    def generate_dataset(self, 
                        use_feature_extractor: bool = False):
        """
        Generate complete training dataset
        
        Args:
            use_feature_extractor: Whether to process PCAPs into features
        """
        logger.info("Starting dataset generation...")
        logger.info(f"Total scenarios: {len(self.scenarios)}")
        
        total_samples = sum(s['repeat'] for s in self.scenarios)
        logger.info(f"Target samples: {total_samples}")
        
        all_metadata = []
        
        for scenario in self.scenarios:
            logger.info(f"\n{'='*60}")
            logger.info(f"Scenario: {scenario['name']}")
            logger.info(f"{'='*60}")
            
            for i in range(scenario['repeat']):
                logger.info(f"\nIteration {i+1}/{scenario['repeat']}")
                
                # Run simulation and capture PCAP
                pcap_file = self.run_scenario(scenario, i)
                
                if pcap_file and os.path.exists(pcap_file):
                    # Store metadata
                    metadata = {
                        'pcap_file': pcap_file,
                        'scenario': scenario['name'],
                        'label': scenario['label'],
                        'bandwidth_label': scenario['bandwidth_label'],
                        'bandwidth_kbps': scenario['bandwidth_kbps'],
                        'timestamp': datetime.now().isoformat(),
                        'iteration': i,
                        'file_size_bytes': os.path.getsize(pcap_file)
                    }
                    all_metadata.append(metadata)
                    logger.info(f"✓ Iteration {i+1} completed successfully")
                else:
                    logger.warning(f"✗ Iteration {i+1} failed - no PCAP generated")
                
                # Small delay between iterations
                time.sleep(5)
        
        # Save metadata
        if all_metadata:
            metadata_df = pd.DataFrame(all_metadata)
            metadata_file = self.output_dir / "dataset_metadata.csv"
            metadata_df.to_csv(metadata_file, index=False)
            logger.info(f"\n✓ Metadata saved: {metadata_file}")
            
            # Print summary
            logger.info("\n" + "="*60)
            logger.info("DATASET GENERATION COMPLETE")
            logger.info("="*60)
            logger.info(f"Total samples: {len(metadata_df)}")
            logger.info(f"Normal samples: {len(metadata_df[metadata_df['label'] == 'normal'])}")
            logger.info(f"Anomaly samples: {len(metadata_df[metadata_df['label'] == 'anomaly'])}")
            logger.info(f"Total PCAP size: {metadata_df['file_size_bytes'].sum() / 1024 / 1024:.2f} MB")
            logger.info("="*60)
            
            # Show what was captured
            logger.info("\nGenerated files:")
            for _, row in metadata_df.iterrows():
                size_kb = row['file_size_bytes'] / 1024
                logger.info(f"  {row['scenario']:20s} - {size_kb:8.2f} KB - {row['pcap_file']}")
        else:
            logger.error("No data generated! Check logs above for errors.")


# Main execution
if __name__ == "__main__":
    import sys
    
    # Check if running from correct directory
    current_dir = Path.cwd()
    logger.info(f"Current directory: {current_dir}")
    
    # Check if we're in training/ directory
    if not (current_dir / "dataset_generator.py").exists():
        logger.error("Please run this script from the training/ directory!")
        logger.error(f"Current: {current_dir}")
        logger.error("Expected: .../training/")
        sys.exit(1)
    
    # Check if mininet topology exists
    mininet_topo = current_dir.parent / "mininet" / "topology.py"
    if not mininet_topo.exists():
        logger.error(f"Mininet topology not found at: {mininet_topo}")
        sys.exit(1)
    
    logger.info(f"✓ Mininet topology found: {mininet_topo}")
    
    # Step 1: Generate simulated data
    logger.info("\nStarting dataset generation...")
    logger.info("This will take a while - each scenario runs for ~35 seconds")
    logger.info("Press Ctrl+C to stop\n")
    
    generator = MininetwifiScenarioGenerator()
    
    try:
        generator.generate_dataset(use_feature_extractor=False)
    except KeyboardInterrupt:
        logger.info("\n\nDataset generation interrupted by user")
        subprocess.run("sudo mn -c 2>/dev/null", shell=True)
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        subprocess.run("sudo mn -c 2>/dev/null", shell=True)
    
    logger.info("\nDone! Check training_data/pcap_captures/ for generated PCAP files")
    logger.info("You can now upload the CSV files + PCAPs to train models in Google Colab")