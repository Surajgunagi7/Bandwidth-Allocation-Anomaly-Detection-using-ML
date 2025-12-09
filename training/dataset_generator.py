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
                'command': 'ping -c 30 10.0.0.4',  # Changed from wget
                'duration': 35,
                'repeat': 10  # Reduced for testing
            },
            {
                'name': 'video_streaming',
                'label': 'normal',
                'bandwidth_label': 'medium',
                'bandwidth_kbps': 3000,
                'command': 'iperf3 -c 10.0.0.4 -u -b 3M -t 30',
                'duration': 35,
                'repeat': 10
            },
            {
                'name': 'voip_call',
                'label': 'normal',
                'bandwidth_label': 'low',
                'bandwidth_kbps': 128,
                'command': 'iperf3 -c 10.0.0.4 -u -b 128K -t 30',
                'duration': 35,
                'repeat': 10
            },
            {
                'name': 'file_download',
                'label': 'normal',
                'bandwidth_label': 'high',
                'bandwidth_kbps': 8000,
                'command': 'iperf3 -c 10.0.0.4 -t 30',
                'duration': 35,
                'repeat': 10
            },
        ])
        
        # High Bandwidth Scenarios
        self.scenarios.extend([
            {
                'name': 'multi_video_streams',
                'label': 'normal',
                'bandwidth_label': 'high',
                'bandwidth_kbps': 12000,
                'command': 'iperf3 -c 10.0.0.4 -P 3 -u -b 4M -t 30',
                'duration': 35,
                'repeat': 10
            },
        ])
        
        # Anomaly Scenarios
        self.scenarios.extend([
            {
                'name': 'bandwidth_hog',
                'label': 'anomaly',
                'bandwidth_label': 'extreme',
                'bandwidth_kbps': 80000,
                'command': 'iperf3 -c 10.0.0.4 -P 10 -t 30',
                'duration': 35,
                'repeat': 10
            },
        ])
    
    def generate_mininet_topology(self):
        """Get path to real topology script"""
        # Assuming script is run from training/ directory
        real_topo = Path(__file__).parent.parent / "mininet" / "topology.py"
        if not real_topo.exists():
            raise FileNotFoundError(f"topology.py not found at {real_topo}")
        return str(real_topo)
    
    def run_scenario(self, scenario: dict, iteration: int) -> str:
        """Run a single scenario iteration"""
        topo_script = self.generate_mininet_topology()
        pcap_file = self.pcap_dir / f"{scenario['name']}_{iteration}_{int(time.time())}.pcap"
    
        logger.info(f"Running {scenario['name']} (iter {iteration})")
        
        # Clean up any previous Mininet processes
        subprocess.run("sudo mn -c 2>/dev/null", shell=True)
        time.sleep(2)
        
        try:
            # Start Mininet-WiFi in background
            proc = subprocess.Popen(
                ["sudo", "python3", topo_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for network to stabilize
            time.sleep(15)
            
            # Verify Mininet is running
            check = subprocess.run(
                "sudo mn -c 2>&1 | grep -q 'cleanup'",
                shell=True
            )
            
            if check.returncode != 0:
                logger.warning("Mininet may not have started properly")
            
            # Run traffic command on sta1
            # Use mininet CLI to execute command
            cmd = f'sudo python3 -c "from mininet.net import Mininet; from mininet.cli import CLI; import time; net = Mininet.get(); if net: sta1 = net.get(\\"sta1\\"); sta1.cmd(\\"{scenario["command"]} &\\"); time.sleep({scenario["duration"]})"'
            
            # Simpler approach: use mnexec
            cmd = f"sudo mnexec -a $(pgrep -f 'sta1$') {scenario['command']} &"
            subprocess.run(cmd, shell=True)
            
            # Wait for traffic to complete
            time.sleep(scenario['duration'])
            
        except Exception as e:
            logger.error(f"Error running scenario: {e}")
        
        finally:
            # Stop Mininet
            subprocess.run("sudo mn -c 2>/dev/null", shell=True)
            proc.terminate()
            time.sleep(5)
        
        # Find latest PCAP in pcap_captures directory
        try:
            pcap_list = list(self.pcap_dir.glob("*.pcap*"))
            if pcap_list:
                # Get the most recent file
                latest = max(pcap_list, key=os.path.getctime)
                # Rename with scenario name
                new_name = self.pcap_dir / f"{scenario['name']}_{iteration}.pcap"
                if latest != new_name:
                    shutil.move(str(latest), str(new_name))
                logger.info(f"PCAP saved: {new_name}")
                return str(new_name)
            else:
                logger.warning("No PCAP file generated")
                return ""
        except Exception as e:
            logger.error(f"Error handling PCAP file: {e}")
            return ""
    
    def generate_dataset(self, 
                        use_feature_extractor: bool = True,
                        feature_extractor_path: str = "../backend/feature_extractor.py"):
        """
        Generate complete training dataset
        
        Args:
            use_feature_extractor: Whether to process PCAPs into features
            feature_extractor_path: Path to feature extractor script
        """
        logger.info("Starting dataset generation...")
        logger.info(f"Total scenarios: {len(self.scenarios)}")
        
        total_samples = sum(s['repeat'] for s in self.scenarios)
        logger.info(f"Target samples: {total_samples}")
        
        all_metadata = []
        
        for scenario in self.scenarios:
            logger.info(f"\n=== Scenario: {scenario['name']} ===")
            
            for i in range(scenario['repeat']):
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
                        'iteration': i
                    }
                    all_metadata.append(metadata)
                    logger.info(f"  Iteration {i+1}/{scenario['repeat']} completed")
                else:
                    logger.warning(f"  Iteration {i+1} failed - no PCAP generated")
        
        # Save metadata
        metadata_df = pd.DataFrame(all_metadata)
        metadata_file = self.output_dir / "dataset_metadata.csv"
        metadata_df.to_csv(metadata_file, index=False)
        logger.info(f"\nMetadata saved: {metadata_file}")
        
        # Process PCAPs if requested
        if use_feature_extractor and os.path.exists(feature_extractor_path):
            logger.info("\nProcessing PCAPs to extract features...")
            self._process_pcaps_to_features(metadata_df, feature_extractor_path)
        
        logger.info("\n=== Dataset Generation Complete ===")
        logger.info(f"Total samples: {len(metadata_df)}")
        if len(metadata_df) > 0:
            logger.info(f"Normal samples: {len(metadata_df[metadata_df['label'] == 'normal'])}")
            logger.info(f"Anomaly samples: {len(metadata_df[metadata_df['label'] == 'anomaly'])}")
    
    def _process_pcaps_to_features(self, metadata_df: pd.DataFrame, extractor_path: str):
        """Process all PCAP files to extract features"""
        import sys
        sys.path.append(str(Path(extractor_path).parent))
        
        from feature_extractor import process_pcap_file
        
        all_features = []
        
        for idx, row in metadata_df.iterrows():
            pcap_file = row['pcap_file']
            
            if not os.path.exists(pcap_file):
                logger.warning(f"PCAP not found: {pcap_file}")
                continue
            
            try:
                # Extract features
                features = process_pcap_file(pcap_file, output_csv=None)
                
                if not features['all'].empty:
                    # Add labels
                    features['all']['label'] = row['label']
                    features['all']['bandwidth_label'] = row['bandwidth_label']
                    features['all']['bandwidth_kbps'] = row['bandwidth_kbps']
                    features['all']['scenario'] = row['scenario']
                    
                    all_features.append(features['all'])
            
            except Exception as e:
                logger.error(f"Failed to process {pcap_file}: {e}")
            
            if (idx + 1) % 10 == 0:
                logger.info(f"  Processed {idx+1}/{len(metadata_df)} PCAPs")
        
        # Combine all features
        if all_features:
            final_df = pd.concat(all_features, ignore_index=True)
            
            # Save complete dataset
            dataset_file = self.output_dir / "training_dataset.csv"
            final_df.to_csv(dataset_file, index=False)
            logger.info(f"Training dataset saved: {dataset_file}")
            logger.info(f"Final dataset shape: {final_df.shape}")


class PublicDatasetIntegrator:
    """Integrate public datasets (e.g., CIC-IDS2017) for anomaly detection"""
    
    def __init__(self, output_dir: str = "./training_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def process_cicids2017(self, cicids_csv_path: str) -> pd.DataFrame:
        """
        Process CIC-IDS2017 dataset for anomaly detection
        
        Args:
            cicids_csv_path: Path to CIC-IDS2017 CSV file
            
        Returns:
            Processed DataFrame with extracted features
        """
        logger.info(f"Loading CIC-IDS2017 dataset: {cicids_csv_path}")
        
        try:
            df = pd.read_csv(cicids_csv_path)
            logger.info(f"Loaded {len(df)} rows from CIC-IDS2017")
        except Exception as e:
            logger.error(f"Failed to load CIC-IDS2017: {e}")
            return pd.DataFrame()
        
        # Map CIC-IDS2017 columns to our feature names
        column_mapping = {
            'Flow Duration': 'flow_duration',
            'Total Fwd Packets': 'total_packets',
            'Total Length of Fwd Packets': 'total_bytes',
            'Fwd Packet Length Mean': 'avg_packet_size',
            'Fwd Packet Length Std': 'std_packet_size',
            'Flow Bytes/s': 'bytes_per_second',
            'Flow Packets/s': 'packets_per_second',
            'Flow IAT Mean': 'avg_inter_arrival_time',
            'Label': 'label'
        }
        
        # Select and rename columns
        available_cols = [col for col in column_mapping.keys() if col in df.columns]
        df_mapped = df[available_cols].rename(columns=column_mapping)
        
        # Convert label to binary
        df_mapped['label'] = df_mapped['label'].apply(
            lambda x: 'normal' if x == 'BENIGN' else 'anomaly'
        )
        
        logger.info(f"Processed CIC-IDS2017 features: {df_mapped.shape}")
        return df_mapped
    
    def merge_with_simulated_data(self, 
                                  simulated_data_path: str,
                                  cicids_data: pd.DataFrame) -> pd.DataFrame:
        """Merge simulated and public dataset"""
        simulated_df = pd.read_csv(simulated_data_path)
        
        # Combine datasets
        combined_df = pd.concat([simulated_df, cicids_data], ignore_index=True)
        
        # Balance classes
        combined_df = self._balance_classes(combined_df)
        
        output_file = self.output_dir / "combined_training_dataset.csv"
        combined_df.to_csv(output_file, index=False)
        
        logger.info(f"Combined dataset saved: {output_file}")
        logger.info(f"Final shape: {combined_df.shape}")
        
        return combined_df
    
    def _balance_classes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Balance normal and anomaly classes"""
        normal_samples = df[df['label'] == 'normal']
        anomaly_samples = df[df['label'] == 'anomaly']
        
        logger.info(f"Before balancing - Normal: {len(normal_samples)}, Anomaly: {len(anomaly_samples)}")
        
        # Undersample majority class
        min_samples = min(len(normal_samples), len(anomaly_samples))
        
        normal_balanced = normal_samples.sample(n=min_samples, random_state=42)
        anomaly_balanced = anomaly_samples.sample(n=min_samples, random_state=42)
        
        balanced_df = pd.concat([normal_balanced, anomaly_balanced], ignore_index=True)
        balanced_df = balanced_df.sample(frac=1, random_state=42).reset_index(drop=True)
        
        logger.info(f"After balancing - Total: {len(balanced_df)}")
        
        return balanced_df


# Main execution
if __name__ == "__main__":
    import sys
    
    # Check if running from correct directory
    current_dir = Path.cwd()
    logger.info(f"Current directory: {current_dir}")
    
    # Step 1: Generate simulated data
    generator = MininetwifiScenarioGenerator()
    generator.generate_dataset(use_feature_extractor=True)
    
    # Step 2: Integrate public dataset (if available)
    integrator = PublicDatasetIntegrator()
    
    # Example: Process CIC-IDS2017
    cicids_path = "./training_data/CICIDS2017_sample.csv"
    if os.path.exists(cicids_path):
        cicids_data = integrator.process_cicids2017(cicids_path)
        final_dataset = integrator.merge_with_simulated_data(
            "./training_data/training_dataset.csv",
            cicids_data
        )
    else:
        logger.info("CIC-IDS2017 not found. Using only simulated data.")