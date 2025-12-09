from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import logging
from pathlib import Path

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for dashboard frontend

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Directory configuration
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
for directory in [UPLOAD_DIR, PROCESSED_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# Configuration
ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".cap"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB limit

def allowed_file(filename):
    """Check if file has an allowed extension."""
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)

def generate_filename(original_filename):
    """Generate unique filename with timestamp."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    secure_name = secure_filename(original_filename or "capture.pcap")
    
    # Ensure extension is present
    if not allowed_file(secure_name):
        secure_name += ".pcap"
    
    return f"{timestamp}_{secure_name}"

@app.route("/", methods=["GET"])
def home():
    """Health check endpoint."""
    return jsonify({
        "status": "running",
        "service": "Bandwidth Allocation & Anomaly Detection Backend",
        "version": "1.0.0"
    }), 200

@app.route("/traffic", methods=["POST"])
def traffic():
    """
    Receive PCAP files from AP nodes.
    Supports both multipart form uploads and raw binary uploads.
    """
    try:
        saved_path = None
        
        # Case 1: Multipart form upload (with 'capture' field)
        if "capture" in request.files:
            file = request.files["capture"]
            
            if not file or file.filename == "":
                return jsonify({"error": "No file selected"}), 400
            
            # Check file size (if available in content-length)
            if request.content_length and request.content_length > MAX_FILE_SIZE:
                return jsonify({"error": "File too large"}), 413
            
            filename = generate_filename(file.filename)
            saved_path = UPLOAD_DIR / filename
            
            file.save(str(saved_path))
            logger.info(f"Received multipart upload: {filename}")
        
        # Case 2: Raw binary upload
        elif request.data:
            data = request.get_data()
            
            if len(data) > MAX_FILE_SIZE:
                return jsonify({"error": "File too large"}), 413
            
            # Get filename from header or use default
            filename = request.headers.get("X-Filename", "capture.pcap")
            filename = generate_filename(filename)
            saved_path = UPLOAD_DIR / filename
            
            with open(saved_path, "wb") as f:
                f.write(data)
            
            logger.info(f"Received raw binary upload: {filename}")
        
        else:
            return jsonify({"error": "No PCAP data provided"}), 400
        
        # Return success response
        return jsonify({
            "status": "success",
            "filename": saved_path.name,
            "timestamp": datetime.utcnow().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Failed to process upload"
        }), 500

@app.route("/stats", methods=["GET"])
def stats():
    """
    Get basic statistics about uploaded files.
    Useful for dashboard monitoring.
    """
    try:
        upload_files = list(UPLOAD_DIR.glob("*.pcap*"))
        processed_files = list(PROCESSED_DIR.glob("*.pcap*"))
        
        total_upload_size = sum(f.stat().st_size for f in upload_files)
        total_processed_size = sum(f.stat().st_size for f in processed_files)
        
        return jsonify({
            "uploads": {
                "count": len(upload_files),
                "total_size_mb": round(total_upload_size / (1024 * 1024), 2)
            },
            "processed": {
                "count": len(processed_files),
                "total_size_mb": round(total_processed_size / (1024 * 1024), 2)
            },
            "timestamp": datetime.utcnow().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        return jsonify({"error": "Failed to fetch stats"}), 500

@app.route("/health", methods=["GET"])
def health():
    """Health check for monitoring systems."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }), 200

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    logger.info("Starting Flask backend server...")
    logger.info(f"Upload directory: {UPLOAD_DIR}")
    logger.info(f"Processed directory: {PROCESSED_DIR}")
    
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True  # Enable threading for concurrent requests
    )