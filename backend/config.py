# config.py (FINAL VERSION)
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Load .env file

class Config:
    BASE_DIR = Path(__file__).parent
    
    # Directories
    UPLOAD_DIR = BASE_DIR / "uploads"
    PROCESSED_DIR = BASE_DIR / "processed"
    LOGS_DIR = BASE_DIR / "logs"
    MODELS_DIR = BASE_DIR / "models"
    
    # Network
    TOTAL_BANDWIDTH_MBPS = int(os.getenv("TOTAL_BANDWIDTH_MBPS", "100"))
    AP_INTERFACE = os.getenv("AP_INTERFACE", "ap1-wlan1")
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".cap"}
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    # Processing
    PROCESSING_INTERVAL = 5
    CLEANUP_AGE = 3600
    
    # Flask
    DEBUG = os.getenv("FLASK_ENV", "development") == "development"
    HOST = "0.0.0.0"
    PORT = 5000
    
    # ML
    BATCH_SIZE = 10
    PREDICTION_THRESHOLD = 0.7
    
    # AP MACs to exclude
    KNOWN_AP_MACS = {"00:11:22:33:44:55", "aa:bb:cc:dd:ee:ff"}  # fallback

# Auto-switch config
APP_ENV = os.getenv("FLASK_ENV", "development")
config = Config()  # single source of truth