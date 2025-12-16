#!/usr/bin/env python3
"""
Configuration Module
Centralized configuration with dynamic bandwidth detection
"""

import os
import subprocess
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Main configuration class with dynamic capabilities"""
    
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
    AP_INTERFACE = os.getenv("AP_INTERFACE", "ap1-wlan1")
    
    # Dynamic bandwidth - will be detected at runtime
    _total_bandwidth_mbps = None
    
    @classmethod
    def get_total_bandwidth(cls):
        """Get total bandwidth with fallback"""
        if cls._total_bandwidth_mbps is None:
            # Try to get from env first
            env_bw = os.getenv("TOTAL_BANDWIDTH_MBPS")
            if env_bw:
                cls._total_bandwidth_mbps = int(env_bw)
            else:
                # Detect dynamically
                cls._total_bandwidth_mbps = cls.detect_interface_bandwidth()
        return cls._total_bandwidth_mbps
    
    @classmethod
    def set_total_bandwidth(cls, bandwidth_mbps: int):
        """Manually set bandwidth (useful for API calls)"""
        cls._total_bandwidth_mbps = bandwidth_mbps
        logging.getLogger(__name__).info(f"Bandwidth manually set to {bandwidth_mbps} Mbps")
    
    @classmethod
    def detect_interface_bandwidth(cls) -> int:
        """Detect interface bandwidth from system"""
        logger = logging.getLogger(__name__)
        
        try:
            # Try ethtool first
            result = subprocess.run(
                f"ethtool {cls.AP_INTERFACE} 2>/dev/null | grep Speed",
                shell=True,
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if result.returncode == 0 and "Speed:" in result.stdout:
                # Parse "Speed: 1000Mb/s" or similar
                speed_line = result.stdout.strip()
                if "Mb/s" in speed_line:
                    speed_str = speed_line.split("Speed:")[1].strip().replace("Mb/s", "")
                    bandwidth = int(speed_str)
                    logger.info(f"Detected bandwidth via ethtool: {bandwidth} Mbps")
                    return bandwidth
        except Exception as e:
            logger.debug(f"ethtool detection failed: {e}")
        
        # Fallback: try iwconfig for wireless
        try:
            result = subprocess.run(
                f"iwconfig {cls.AP_INTERFACE} 2>/dev/null | grep 'Bit Rate'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if result.returncode == 0 and "Bit Rate" in result.stdout:
                # Parse "Bit Rate=54 Mb/s" or similar
                line = result.stdout.strip()
                if "Mb/s" in line:
                    rate = line.split("=")[1].split("Mb/s")[0].strip()
                    bandwidth = int(float(rate))
                    logger.info(f"Detected bandwidth via iwconfig: {bandwidth} Mbps")
                    return bandwidth
        except Exception as e:
            logger.debug(f"iwconfig detection failed: {e}")
        
        # Final fallback
        logger.warning(f"Could not detect bandwidth for {cls.AP_INTERFACE}, using default 100 Mbps")
        return 100
    
    @property
    def TOTAL_BANDWIDTH_MBPS(self):
        """Property for backward compatibility"""
        return self.get_total_bandwidth()
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".cap"}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    
    # Processing
    PROCESSING_INTERVAL = int(os.getenv("PROCESSING_INTERVAL", "5"))
    CLEANUP_AGE = int(os.getenv("CLEANUP_AGE", "3600"))
    
    # Flask
    DEBUG = os.getenv("FLASK_ENV", "development") == "development"
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5000"))
    
    # ML Configuration
    BATCH_SIZE = int(os.getenv("ML_BATCH_SIZE", "10"))
    PREDICTION_THRESHOLD = float(os.getenv("PREDICTION_THRESHOLD", "0.7"))
    
    # Known AP MAC addresses (will be auto-detected)
    KNOWN_AP_MACS = set()
    
    # Traffic Control
    TC_UPDATE_INTERVAL = int(os.getenv("TC_UPDATE_INTERVAL", "10"))
    TC_CHANGE_THRESHOLD = float(os.getenv("TC_CHANGE_THRESHOLD", "0.15"))
    
    # Bandwidth Allocation - MINIMUM allocations to ensure usability
    MIN_BANDWIDTH_KBPS = 512  # At least 512 kbps per device
    
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
    ANOMALY_BANDWIDTH_CAP = int(os.getenv("ANOMALY_BANDWIDTH_CAP", "1000"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Anomaly Mode
    NO_ANOMALY_MODE = os.getenv("NO_ANOMALY_MODE", "false").lower() == "true"
    
    @classmethod
    def setup_logging(cls):
        """Setup logging to both file and console with appropriate levels"""
        # Create logs directory
        cls.LOGS_DIR.mkdir(exist_ok=True, parents=True)
        
        # Main application log
        main_log = cls.LOGS_DIR / "app.log"
        
        # Remove existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # File handler - captures everything
        file_handler = logging.FileHandler(main_log)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(cls.LOG_FORMAT)
        file_handler.setFormatter(file_formatter)
        
        # Console handler - only important messages
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)  # Only warnings and errors to console
        console_formatter = logging.Formatter('%(levelname)s: %(name)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Configure root logger
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Make specific loggers less verbose
        logging.getLogger('scapy').setLevel(logging.ERROR)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        errors = []
        
        # Check if models exist
        required_models = [
            cls.MODELS_DIR / "bandwidth_predictor.pkl",
            cls.MODELS_DIR / "anomaly_detector.pkl",
        ]
        
        missing_models = [str(m) for m in required_models if not m.exists()]
        if missing_models:
            errors.append(f"Missing model files: {missing_models}")
        
        # Check network interface
        if os.name != 'nt':
            try:
                result = subprocess.run(
                    f"ip link show {cls.AP_INTERFACE}",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode != 0:
                    errors.append(f"Network interface {cls.AP_INTERFACE} not found")
            except Exception as e:
                errors.append(f"Failed to check network interface: {e}")
        
        if errors:
            logger = logging.getLogger(__name__)
            logger.warning("Configuration validation warnings:")
            for error in errors:
                logger.warning(f"  - {error}")
            return False
        
        return True
    
    @classmethod
    def print_config(cls):
        """Print current configuration"""
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("CONFIGURATION")
        logger.info("=" * 60)
        logger.info(f"Base Directory: {cls.BASE_DIR}")
        logger.info(f"Network Interface: {cls.AP_INTERFACE}")
        logger.info(f"Total Bandwidth: {cls.get_total_bandwidth()} Mbps")
        logger.info(f"Min Bandwidth per Device: {cls.MIN_BANDWIDTH_KBPS} kbps")
        logger.info(f"Flask Host: {cls.HOST}:{cls.PORT}")
        logger.info(f"Processing Interval: {cls.PROCESSING_INTERVAL}s")
        logger.info(f"TC Update Interval: {cls.TC_UPDATE_INTERVAL}s")
        logger.info(f"Anomaly Detection: {'DISABLED' if cls.NO_ANOMALY_MODE else 'ENABLED'}")
        logger.info("=" * 60)


# Create directories on import
Config.create_directories()

# Setup logging
Config.setup_logging()

# Export config instance
config = Config()