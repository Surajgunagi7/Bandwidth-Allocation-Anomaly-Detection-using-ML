# app.py — FINAL VERSION (copy-paste this entire file)
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import logging
from pathlib import Path
from datetime import datetime
import threading
import time
import shutil

# Import config and ML pipeline
from config import config
from ml_integration import PipelineController

# Flask setup
app = Flask(__name__)
CORS(app)
app.secret_key = config.SECRET_KEY

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize ML + enforcement pipeline
pipeline = PipelineController(
    models_dir=str(config.MODELS_DIR),
    interface=config.AP_INTERFACE,
    update_interval=10
)

# Background worker: watches uploads/ and processes new PCAPs
def pcap_processing_worker():
    logger.info("Background PCAP processing worker started")
    seen_files = set()

    while True:
        try:
            pcap_files = list(config.UPLOAD_DIR.glob("*.pcap*"))
            new_files = [f for f in pcap_files if f.name not in seen_files]

            for pcap_file in new_files:
                logger.info(f"Processing: {pcap_file.name}")
                result = pipeline.process_pcap(str(pcap_file))

                if result.get("status") == "success":
                    dest = config.PROCESSED_DIR / pcap_file.name
                    shutil.move(str(pcap_file), dest)
                    logger.info(f"Processed and moved: {pcap_file.name}")
                else:
                    logger.warning(f"Failed: {pcap_file.name} → {result.get('message')}")

                seen_files.add(pcap_file.name)
                if len(seen_files) > 200:
                    seen_files = set(list(seen_files)[-200:])  

            time.sleep(config.PROCESSING_INTERVAL)

        except Exception as e:
            logger.error(f"Worker crash: {e}")
            time.sleep(5)

# Start worker thread
threading.Thread(target=pcap_processing_worker, daemon=True).start()

# Helper
def generate_filename(original_filename):
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    secure_name = secure_filename(original_filename or "capture.pcap")
    if not any(secure_name.lower().endswith(ext) for ext in config.ALLOWED_EXTENSIONS):
        secure_name += ".pcap"
    return f"{timestamp}_{secure_name}"

# Routes
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "running", "service": "ML-Powered WiFi Controller v1.0"}), 200

@app.route("/traffic", methods=["POST"])
def traffic():
    """Your perfect code — pasted exactly"""
    try:
        saved_path = None
        
        # Case 1: Multipart upload
        if "capture" in request.files:
            file = request.files["capture"]
            if not file or file.filename == "":
                return jsonify({"error": "No file selected"}), 400
            
            if request.content_length and request.content_length > config.MAX_FILE_SIZE:
                return jsonify({"error": "File too large"}), 413
            
            filename = generate_filename(file.filename)
            saved_path = config.UPLOAD_DIR / filename
            file.save(str(saved_path))
            logger.info(f"Multipart upload saved: {filename}")
        
        # Case 2: Raw binary upload
        elif request.data:
            data = request.get_data()
            if len(data) > config.MAX_FILE_SIZE:
                return jsonify({"error": "File too large"}), 413
            
            filename = request.headers.get("X-Filename", "capture.pcap")
            filename = generate_filename(filename)
            saved_path = config.UPLOAD_DIR / filename
            
            with open(saved_path, "wb") as f:
                f.write(data)
            logger.info(f"Raw upload saved: {filename}")
        
        else:
            return jsonify({"error": "No PCAP data provided"}), 400
        
        return jsonify({
            "status": "success",
            "filename": saved_path.name,
            "size_bytes": saved_path.stat().st_size,
            "timestamp": datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({"error": "Failed to process upload"}), 500

@app.route("/stats", methods=["GET"])
def stats():
    pipeline_stats = pipeline.get_statistics()
    return jsonify({
        "total_bandwidth_mbps": config.TOTAL_BANDWIDTH_MBPS,
        "ap_interface": config.AP_INTERFACE,
        "active_devices": pipeline_stats.get("active_devices", 0),
        "uploads_pending": len(list(config.UPLOAD_DIR.glob("*.pcap*"))),
        "processed_total": len(list(config.PROCESSED_DIR.glob("*.pcap*"))),
        "uptime": time.time() - start_time
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200

# Global start time for uptime
start_time = time.time()

if __name__ == "__main__":
    logger.info("=== ML-Powered WiFi Controller STARTED ===")
    logger.info(f"Total bandwidth: {config.TOTAL_BANDWIDTH_MBPS} Mbps")
    logger.info(f"AP interface: {config.AP_INTERFACE}")
    logger.info(f"Upload folder: {config.UPLOAD_DIR}")
    
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)