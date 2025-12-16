#!/usr/bin/env python3
"""
Configuration Module
Centralized configuration for the entire project
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Main configuration class"""
    
    # Base paths
    BASE_DIR = Path(__file__).parent.absolute()
    
    # Directories
    UPLOAD_DIR = BASE_DIR / "uploads"
    PROCESSED_DIR = BASE_DIR / "processed"
    LOGS_DIR = BASE_DIR / "logs"
    MODELS_DIR = BASE_DIR / "models"
    
    # Create directories if they don't exist
    @classmethod
    def create_directories(cls):
        """Create necessary directories"""
        for directory in [cls.UPLOAD_DIR, cls.PROCESSED_DIR, cls.LOGS_DIR, cls.MODELS_DIR]:
            directory.mkdir(exist_ok=True, parents=True)
    
    # Network Configuration
    TOTAL_BANDWIDTH_MBPS = int(os.getenv("TOTAL_BANDWIDTH_MBPS", "100"))
    AP_INTERFACE = os.getenv("AP_INTERFACE", "ap1-wlan1")
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".cap"}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    
    # Processing
    PROCESSING_INTERVAL = int(os.getenv("PROCESSING_INTERVAL", "5"))
    CLEANUP_AGE = int(os.getenv("CLEANUP_AGE", "3600"))  # 1 hour
    
    # Flask
    DEBUG = os.getenv("FLASK_ENV", "development") == "development"
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5000"))
    
    # ML Configuration
    BATCH_SIZE = int(os.getenv("ML_BATCH_SIZE", "10"))
    PREDICTION_THRESHOLD = float(os.getenv("PREDICTION_THRESHOLD", "0.7"))
    
    # Known AP MAC addresses to exclude from processing
    # These will be detected at runtime and added to this set
    KNOWN_AP_MACS = set()
    
    # Add fallback MACs
    _FALLBACK_AP_MACS = {"00:11:22:33:44:55", "aa:bb:cc:dd:ee:ff"}
    KNOWN_AP_MACS.update(_FALLBACK_AP_MACS)
    
    # Traffic Control
    TC_UPDATE_INTERVAL = int(os.getenv("TC_UPDATE_INTERVAL", "10"))
    TC_CHANGE_THRESHOLD = float(os.getenv("TC_CHANGE_THRESHOLD", "0.15"))
    
    # Bandwidth Allocation Priorities
    PRIORITY_HIGH = 1
    PRIORITY_MEDIUM = 2
    PRIORITY_LOW = 3
    
    # Traffic Classes
    TRAFFIC_CLASS_MAP = {
        'voip': PRIORITY_HIGH,
        'video_conference': PRIORITY_HIGH,
        'video': PRIORITY_HIGH,
        'streaming': PRIORITY_MEDIUM,
        'web': PRIORITY_MEDIUM,
        'bulk': PRIORITY_LOW,
        'file_transfer': PRIORITY_LOW,
        'unknown': PRIORITY_MEDIUM,
    }
    
    # Anomaly Detection
    ANOMALY_BANDWIDTH_CAP = int(os.getenv("ANOMALY_BANDWIDTH_CAP", "1000"))  # 1 Mbps
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Anomaly Mode
    NO_ANOMALY_MODE = os.getenv("NO_ANOMALY_MODE", "false").lower() == "true"
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        errors = []
        
        # Check if models exist
        required_models = [
            cls.MODELS_DIR / "bandwidth_predictor.pkl",
            cls.MODELS_DIR / "anomaly_detector.pkl",
            cls.MODELS_DIR / "feature_scaler.pkl"
        ]
        
        missing_models = [str(m) for m in required_models if not m.exists()]
        if missing_models:
            errors.append(f"Missing model files: {missing_models}")
        
        # Check network interface (only if running on Linux)
        if os.name != 'nt':  # Not Windows
            import subprocess
            try:
                result = subprocess.run(
                    f"ip link show {cls.AP_INTERFACE}",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    errors.append(f"Network interface {cls.AP_INTERFACE} not found")
            except Exception as e:
                errors.append(f"Failed to check network interface: {e}")
        
        if errors:
            print("⚠️  Configuration Warnings:")
            for error in errors:
                print(f"   - {error}")
            return False
        
        return True
    
    @classmethod
    def print_config(cls):
        """Print current configuration"""
        print("\n" + "="*60)
        print("CONFIGURATION")
        print("="*60)
        print(f"Base Directory: {cls.BASE_DIR}")
        print(f"Models Directory: {cls.MODELS_DIR}")
        print(f"Upload Directory: {cls.UPLOAD_DIR}")
        print(f"Processed Directory: {cls.PROCESSED_DIR}")
        print(f"Logs Directory: {cls.LOGS_DIR}")
        print(f"Network Interface: {cls.AP_INTERFACE}")
        print(f"Total Bandwidth: {cls.TOTAL_BANDWIDTH_MBPS} Mbps")
        print(f"Flask Debug: {cls.DEBUG}")
        print(f"Flask Host: {cls.HOST}")
        print(f"Flask Port: {cls.PORT}")
        print(f"Processing Interval: {cls.PROCESSING_INTERVAL}s")
        print(f"TC Update Interval: {cls.TC_UPDATE_INTERVAL}s")
        print(f"Log Level: {cls.LOG_LEVEL}")
        print("="*60 + "\n")


# Create directories on import
Config.create_directories()

# Export config instance
config = Config()

