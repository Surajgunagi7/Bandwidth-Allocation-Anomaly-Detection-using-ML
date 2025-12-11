#!/usr/bin/env python3
"""
app.py — ROBUST VERSION with Enhanced File Handling
Fixes race conditions and file access errors
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import logging
from pathlib import Path
from datetime import datetime, UTC
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize ML + enforcement pipeline
pipeline = PipelineController(
    models_dir=str(config.MODELS_DIR),
    interface=config.AP_INTERFACE,
    update_interval=10
)

# Thread lock for file operations
file_lock = threading.Lock()


def pcap_processing_worker():
    """
    ENHANCED: Robust PCAP processing worker with proper file handling
    - File stability checks (no partial uploads)
    - Batch processing (handles multiple files per cycle)
    - Error isolation (one bad file doesn't block others)
    - Race condition protection
    - Atomic file operations
    """
    logger.info("Background PCAP processing worker started")
    
    # Track processed files with timestamps to prevent reprocessing
    processed_files = {}  # {filename: timestamp}
    
    # Constants
    FILE_STABLE_TIME = 2.0  # Wait 2 seconds after last modification
    MAX_FILES_PER_BATCH = 5  # Process up to 5 files per iteration
    CLEANUP_THRESHOLD = 500  # Clean tracking dict when it grows too large

    while True:
        try:
            # Acquire lock for file operations
            with file_lock:
                # Get all PCAP files in upload directory
                try:
                    pcap_files = list(config.UPLOAD_DIR.glob("*.pcap*"))
                except Exception as e:
                    logger.error(f"Error listing upload directory: {e}")
                    time.sleep(config.PROCESSING_INTERVAL)
                    continue
                
                # Filter out files we've already processed
                new_files = []
                current_time = time.time()
                
                for pcap_file in pcap_files:
                    # Skip if already processed
                    if pcap_file.name in processed_files:
                        continue
                    
                    # Check if file exists and is stable
                    try:
                        if not pcap_file.exists():
                            logger.debug(f"File disappeared: {pcap_file.name}")
                            processed_files[pcap_file.name] = current_time
                            continue
                        
                        file_stat = pcap_file.stat()
                        file_age = current_time - file_stat.st_mtime
                        
                        # Only process if file hasn't been modified recently
                        if file_age >= FILE_STABLE_TIME and file_stat.st_size > 0:
                            new_files.append((pcap_file, file_stat.st_size))
                        else:
                            logger.debug(f"Skipping {pcap_file.name} - still being written (age: {file_age:.2f}s)")
                    except (OSError, FileNotFoundError) as e:
                        logger.warning(f"Cannot stat {pcap_file.name}: {e}")
                        processed_files[pcap_file.name] = current_time
                        continue
                
                # Sort by size (process smaller files first for faster feedback)
                new_files.sort(key=lambda x: x[1])
                
                # Process batch of files
                files_to_process = new_files[:MAX_FILES_PER_BATCH]
                
                if files_to_process:
                    logger.info(f"Found {len(new_files)} stable file(s), processing batch of {len(files_to_process)}")
            
            # Release lock before processing (processing doesn't need lock)
            for pcap_file, file_size in files_to_process:
                try:
                    # Double-check file still exists before processing
                    if not pcap_file.exists():
                        logger.warning(f"File disappeared before processing: {pcap_file.name}")
                        with file_lock:
                            processed_files[pcap_file.name] = current_time
                        continue
                    
                    logger.info(f"Processing: {pcap_file.name} ({file_size} bytes)")
                    
                    # Convert to absolute path for safety
                    pcap_path_str = str(pcap_file.absolute())
                    
                    # Process the PCAP
                    result = pipeline.process_pcap(pcap_path_str)
                    
                    # Acquire lock for file move operation
                    with file_lock:
                        # Verify file still exists after processing
                        if not pcap_file.exists():
                            logger.warning(f"File disappeared during processing: {pcap_file.name}")
                            processed_files[pcap_file.name] = current_time
                            continue
                        
                        if result.get("status") == "success":
                            # Move to processed directory
                            dest = config.PROCESSED_DIR / pcap_file.name
                            
                            # Handle potential name collision
                            counter = 1
                            original_dest = dest
                            while dest.exists():
                                stem = original_dest.stem
                                suffix = original_dest.suffix
                                dest = config.PROCESSED_DIR / f"{stem}_{counter}{suffix}"
                                counter += 1
                            
                            try:
                                shutil.move(str(pcap_file), str(dest))
                                logger.info(f"✓ Processed and moved: {pcap_file.name} → {dest.name}")
                            except FileNotFoundError:
                                logger.warning(f"File already moved: {pcap_file.name}")
                            except Exception as move_error:
                                logger.error(f"Error moving file {pcap_file.name}: {move_error}")
                            
                        else:
                            # Processing failed - move to error directory
                            error_msg = result.get('message', 'Unknown error')
                            logger.error(f"✗ Processing failed for {pcap_file.name}: {error_msg}")
                            
                            # Move to error directory
                            error_dir = config.UPLOAD_DIR.parent / "errors"
                            error_dir.mkdir(exist_ok=True)
                            
                            error_dest = error_dir / f"error_{pcap_file.name}"
                            counter = 1
                            original_error_dest = error_dest
                            while error_dest.exists():
                                stem = original_error_dest.stem
                                suffix = original_error_dest.suffix
                                error_dest = error_dir / f"{stem}_{counter}{suffix}"
                                counter += 1
                            
                            try:
                                if pcap_file.exists():
                                    shutil.move(str(pcap_file), str(error_dest))
                                    logger.info(f"Moved failed file to: {error_dest}")
                            except FileNotFoundError:
                                logger.warning(f"File already moved: {pcap_file.name}")
                            except Exception as move_error:
                                logger.error(f"Error moving failed file: {move_error}")
                        
                        # Mark as processed
                        processed_files[pcap_file.name] = current_time
                    
                except FileNotFoundError as fnf_error:
                    logger.warning(f"File not found during processing {pcap_file.name}: {fnf_error}")
                    with file_lock:
                        processed_files[pcap_file.name] = current_time
                    
                except Exception as e:
                    logger.error(f"Error processing {pcap_file.name}: {e}", exc_info=True)
                    # Mark as processed to avoid infinite retry loop
                    with file_lock:
                        processed_files[pcap_file.name] = current_time
                    
                    # Try to move to error directory
                    try:
                        with file_lock:
                            if pcap_file.exists():
                                error_dir = config.UPLOAD_DIR.parent / "errors"
                                error_dir.mkdir(exist_ok=True)
                                error_dest = error_dir / f"error_{pcap_file.name}"
                                shutil.move(str(pcap_file), str(error_dest))
                                logger.info(f"Moved error file to: {error_dest}")
                    except Exception as move_error:
                        logger.error(f"Could not move error file: {move_error}")
            
            # Cleanup old entries from tracking dict
            with file_lock:
                if len(processed_files) > CLEANUP_THRESHOLD:
                    # Keep only the most recent entries
                    sorted_items = sorted(processed_files.items(), key=lambda x: x[1], reverse=True)
                    processed_files = dict(sorted_items[:CLEANUP_THRESHOLD // 2])
                    logger.info(f"Cleaned up processed files tracking (kept {len(processed_files)} entries)")
            
            # Sleep interval
            time.sleep(config.PROCESSING_INTERVAL)

        except Exception as e:
            logger.error(f"Worker thread crashed: {e}", exc_info=True)
            time.sleep(5)


# Start worker thread
worker_thread = threading.Thread(target=pcap_processing_worker, daemon=True)
worker_thread.start()


def generate_filename(original_filename):
    """Generate unique timestamped filename"""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
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
    """
    Upload PCAP file endpoint
    ENHANCED: Better error handling and file safety
    """
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
            
            # Save with lock to prevent race conditions
            with file_lock:
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
            
            # Save with lock to prevent race conditions
            with file_lock:
                with open(saved_path, "wb") as f:
                    f.write(data)
            
            logger.info(f"Raw upload saved: {filename}")
        
        else:
            return jsonify({"error": "No PCAP data provided"}), 400
        
        # Verify file was saved successfully
        if not saved_path.exists():
            logger.error(f"File not found after save: {saved_path}")
            return jsonify({"error": "File save failed"}), 500
        
        return jsonify({
            "status": "success",
            "filename": saved_path.name,
            "size_bytes": saved_path.stat().st_size,
            "timestamp": datetime.now(UTC).isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        return jsonify({"error": "Failed to process upload"}), 500


@app.route("/stats", methods=["GET"])
def stats():
    """Get system statistics"""
    try:
        pipeline_stats = pipeline.get_statistics()
        
        # Count files in various states (with lock)
        with file_lock:
            uploads_pending = len(list(config.UPLOAD_DIR.glob("*.pcap*")))
            processed_total = len(list(config.PROCESSED_DIR.glob("*.pcap*")))
            
            # Check for error directory
            error_dir = config.UPLOAD_DIR.parent / "errors"
            errors_total = len(list(error_dir.glob("*.pcap*"))) if error_dir.exists() else 0
        
        return jsonify({
            "total_bandwidth_mbps": config.TOTAL_BANDWIDTH_MBPS,
            "ap_interface": config.AP_INTERFACE,
            "active_devices": pipeline_stats.get("active_devices", 0),
            "uploads_pending": uploads_pending,
            "processed_total": processed_total,
            "errors_total": errors_total,
            "uptime": time.time() - start_time,
            "worker_alive": worker_thread.is_alive()
        })
    except Exception as e:
        logger.error(f"Stats error: {e}", exc_info=True)
        return jsonify({"error": "Failed to get stats"}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    worker_status = "healthy" if worker_thread.is_alive() else "worker_dead"
    return jsonify({
        "status": worker_status,
        "worker_thread": worker_thread.is_alive()
    }), 200


# Global start time for uptime
start_time = time.time()

if __name__ == "__main__":
    logger.info("=== ML-Powered WiFi Controller STARTED ===")
    logger.info(f"Total bandwidth: {config.TOTAL_BANDWIDTH_MBPS} Mbps")
    logger.info(f"AP interface: {config.AP_INTERFACE}")
    logger.info(f"Upload folder: {config.UPLOAD_DIR}")
    logger.info(f"Processing interval: {config.PROCESSING_INTERVAL}s")
    logger.info(f"Max batch size: 5 files per cycle")
    logger.info(f"File stability wait: 2.0s")
    logger.info(f"Thread-safe file operations: ENABLED")
    
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)