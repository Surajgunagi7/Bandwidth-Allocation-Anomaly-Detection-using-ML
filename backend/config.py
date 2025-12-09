import os
from pathlib import Path

class Config:
    """Base configuration."""
    BASE_DIR = Path(__file__).parent
    
    # Directories
    UPLOAD_DIR = BASE_DIR / "uploads"
    PROCESSED_DIR = BASE_DIR / "processed"
    LOGS_DIR = BASE_DIR / "logs"
    MODELS_DIR = BASE_DIR / "models"
    
    # File upload settings
    ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".cap"}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    
    # Processing settings
    PROCESSING_INTERVAL = 5  # seconds
    CLEANUP_AGE = 3600  # seconds (1 hour)
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = True
    HOST = "0.0.0.0"
    PORT = 5000
    
    # ML settings
    BATCH_SIZE = 10
    PREDICTION_THRESHOLD = 0.7
    
    # Logging
    LOG_LEVEL = "INFO"
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')

# Default config
config = DevelopmentConfig()