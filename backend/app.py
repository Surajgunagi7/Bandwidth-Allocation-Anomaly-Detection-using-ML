#!/usr/bin/env python3
"""
Flask Backend with Frontend API Endpoints
NEW: Adds endpoints for dashboard control and monitoring
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

from config import config
from ml_integration import PipelineController

app = Flask(__name__)
CORS(app)
app.secret_key = config.SECRET_KEY

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize pipeline
pipeline = PipelineController(
    models_dir=str(config.MODELS_DIR),
    interface=config.AP_INTERFACE,
    update_interval=config.TC_UPDATE_INTERVAL
)

file_lock = threading.Lock()


def pcap_processing_worker():
    """Background worker for PCAP processing"""
    logger.info("Background worker started")
    processed_files = {}
    FILE_STABLE_TIME = 2.0
    MAX_FILES_PER_BATCH = 5
    CLEANUP_THRESHOLD = 500

    while True:
        try:
            with file_lock:
                try:
                    pcap_files = list(config.UPLOAD_DIR.glob("*.pcap*"))
                except Exception as e:
                    logger.error(f"Error listing uploads: {e}")
                    time.sleep(config.PROCESSING_INTERVAL)
                    continue
                
                new_files = []
                current_time = time.time()
                
                for pcap_file in pcap_files:
                    if pcap_file.name in processed_files:
                        continue
                    
                    try:
                        if not pcap_file.exists():
                            processed_files[pcap_file.name] = current_time
                            continue
                        
                        file_stat = pcap_file.stat()
                        file_age = current_time - file_stat.st_mtime
                        
                        if file_age >= FILE_STABLE_TIME and file_stat.st_size > 0:
                            new_files.append((pcap_file, file_stat.st_size))
                    except Exception as e:
                        logger.warning(f"Cannot stat {pcap_file.name}: {e}")
                        processed_files[pcap_file.name] = current_time
                        continue
                
                new_files.sort(key=lambda x: x[1])
                files_to_process = new_files[:MAX_FILES_PER_BATCH]
                
                if files_to_process:
                    logger.info(f"Processing batch of {len(files_to_process)} file(s)")
            
            for pcap_file, file_size in files_to_process:
                try:
                    if not pcap_file.exists():
                        with file_lock:
                            processed_files[pcap_file.name] = current_time
                        continue
                    
                    logger.info(f"Processing: {pcap_file.name} ({file_size} bytes)")
                    pcap_path_str = str(pcap_file.absolute())
                    result = pipeline.process_pcap(pcap_path_str)
                    
                    with file_lock:
                        if not pcap_file.exists():
                            processed_files[pcap_file.name] = current_time
                            continue
                        
                        if result.get("status") == "success":
                            dest = config.PROCESSED_DIR / pcap_file.name
                            counter = 1
                            original_dest = dest
                            while dest.exists():
                                dest = config.PROCESSED_DIR / f"{original_dest.stem}_{counter}{original_dest.suffix}"
                                counter += 1
                            
                            try:
                                shutil.move(str(pcap_file), str(dest))
                                logger.info(f"✓ Moved: {pcap_file.name}")
                            except Exception as move_error:
                                logger.error(f"Move failed: {move_error}")
                        else:
                            error_dir = config.UPLOAD_DIR.parent / "errors"
                            error_dir.mkdir(exist_ok=True)
                            error_dest = error_dir / f"error_{pcap_file.name}"
                            try:
                                if pcap_file.exists():
                                    shutil.move(str(pcap_file), str(error_dest))
                            except Exception as e:
                                logger.error(f"Error move failed: {e}")
                        
                        processed_files[pcap_file.name] = current_time
                    
                except Exception as e:
                    logger.error(f"Processing error for {pcap_file.name}: {e}")
                    with file_lock:
                        processed_files[pcap_file.name] = current_time
            
            with file_lock:
                if len(processed_files) > CLEANUP_THRESHOLD:
                    sorted_items = sorted(processed_files.items(), key=lambda x: x[1], reverse=True)
                    processed_files = dict(sorted_items[:CLEANUP_THRESHOLD // 2])
            
            time.sleep(config.PROCESSING_INTERVAL)

        except Exception as e:
            logger.error(f"Worker crashed: {e}", exc_info=True)
            time.sleep(5)


worker_thread = threading.Thread(target=pcap_processing_worker, daemon=True)
worker_thread.start()


def generate_filename(original_filename):
    """Generate timestamped filename"""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    secure_name = secure_filename(original_filename or "capture.pcap")
    if not any(secure_name.lower().endswith(ext) for ext in config.ALLOWED_EXTENSIONS):
        secure_name += ".pcap"
    return f"{timestamp}_{secure_name}"


# ============= CORE ROUTES =============

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "running", "service": "ML WiFi Controller v2.0"}), 200


@app.route("/traffic", methods=["POST"])
def traffic():
    """Upload PCAP file"""
    try:
        saved_path = None
        
        if "capture" in request.files:
            file = request.files["capture"]
            if not file or file.filename == "":
                return jsonify({"error": "No file selected"}), 400
            
            if request.content_length and request.content_length > config.MAX_FILE_SIZE:
                return jsonify({"error": "File too large"}), 413
            
            filename = generate_filename(file.filename)
            saved_path = config.UPLOAD_DIR / filename
            
            with file_lock:
                file.save(str(saved_path))
            
            logger.info(f"Upload saved: {filename}")
        
        elif request.data:
            data = request.get_data()
            if len(data) > config.MAX_FILE_SIZE:
                return jsonify({"error": "File too large"}), 413
            
            filename = request.headers.get("X-Filename", "capture.pcap")
            filename = generate_filename(filename)
            saved_path = config.UPLOAD_DIR / filename
            
            with file_lock:
                with open(saved_path, "wb") as f:
                    f.write(data)
            
            logger.info(f"Raw upload saved: {filename}")
        
        else:
            return jsonify({"error": "No PCAP data"}), 400
        
        if not saved_path.exists():
            return jsonify({"error": "Save failed"}), 500
        
        return jsonify({
            "status": "success",
            "filename": saved_path.name,
            "size_bytes": saved_path.stat().st_size,
            "timestamp": datetime.now(UTC).isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        return jsonify({"error": "Upload failed"}), 500


@app.route("/stats", methods=["GET"])
def stats():
    """Get system statistics"""
    try:
        pipeline_stats = pipeline.get_statistics()
        
        with file_lock:
            uploads_pending = len(list(config.UPLOAD_DIR.glob("*.pcap*")))
            processed_total = len(list(config.PROCESSED_DIR.glob("*.pcap*")))
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
            "worker_alive": worker_thread.is_alive(),
            "policy_mode": pipeline_stats.get("policy_mode", "auto"),
            "active_overrides": pipeline_stats.get("active_overrides", 0)
        })
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": "Stats failed"}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    status = "healthy" if worker_thread.is_alive() else "worker_dead"
    return jsonify({"status": status, "worker_thread": worker_thread.is_alive()}), 200


# ============= NEW FRONTEND API ROUTES =============

@app.route("/api/devices", methods=["GET"])
def get_devices():
    """Get all active device allocations"""
    try:
        stats = pipeline.get_statistics()
        devices = stats.get("allocations", [])
        
        # Enrich with history if available
        if pipeline.history:
            last_prediction = pipeline.history[-1].get("predictions", [])
            pred_map = {p['mac_address']: p for p in last_prediction}
            
            for device in devices:
                mac = device['mac']
                if mac in pred_map:
                    device['traffic_class'] = pred_map[mac].get('traffic_class', 'unknown')
                    device['is_anomaly'] = pred_map[mac].get('is_anomaly', False)
                    device['anomaly_score'] = pred_map[mac].get('anomaly_score', 0.0)
        
        return jsonify({"devices": devices}), 200
    except Exception as e:
        logger.error(f"Get devices error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/anomalies", methods=["GET"])
def get_anomalies():
    """Get recent anomaly alerts"""
    try:
        anomalies = []
        
        # Extract anomalies from recent history
        for entry in pipeline.history[-10:]:
            timestamp = entry['timestamp']
            for pred in entry['predictions']:
                if pred.get('is_anomaly', False):
                    anomalies.append({
                        'mac_address': pred['mac_address'],
                        'timestamp': timestamp,
                        'anomaly_score': pred.get('anomaly_score', 0.0),
                        'traffic_class': pred.get('traffic_class', 'unknown'),
                        'bandwidth_kbps': pred.get('predicted_bandwidth_kbps', 0)
                    })
        
        # Sort by timestamp (newest first)
        anomalies.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({"anomalies": anomalies[:20]}), 200  # Last 20
    except Exception as e:
        logger.error(f"Get anomalies error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/history", methods=["GET"])
def get_history():
    """Get prediction history"""
    try:
        limit = int(request.args.get('limit', 10))
        history = pipeline.history[-limit:]
        return jsonify({"history": history}), 200
    except Exception as e:
        logger.error(f"Get history error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/policy/mode", methods=["POST"])
def set_policy_mode():
    """Set global bandwidth mode"""
    try:
        data = request.get_json()
        mode = data.get('mode', 'auto')
        
        if mode not in ['auto', 'equal', 'manual']:
            return jsonify({"error": "Invalid mode"}), 400
        
        pipeline.set_mode(mode)
        
        return jsonify({"status": "success", "mode": mode}), 200
    except Exception as e:
        logger.error(f"Set mode error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/policy/override", methods=["POST"])
def set_device_override():
    """Set manual override for a device"""
    try:
        data = request.get_json()
        mac = data.get('mac_address')
        bandwidth_kbps = data.get('bandwidth_kbps')
        priority = data.get('priority', 2)
        duration_sec = data.get('duration_sec')
        
        if not mac or not bandwidth_kbps:
            return jsonify({"error": "Missing mac_address or bandwidth_kbps"}), 400
        
        pipeline.set_device_override(mac, bandwidth_kbps, priority, duration_sec)
        
        return jsonify({"status": "success", "mac": mac}), 200
    except Exception as e:
        logger.error(f"Override error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/policy/override/<mac_address>", methods=["DELETE"])
def clear_device_override(mac_address):
    """Clear manual override"""
    try:
        pipeline.clear_device_override(mac_address)
        return jsonify({"status": "success", "mac": mac_address}), 200
    except Exception as e:
        logger.error(f"Clear override error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/tc/status", methods=["GET"])
def get_tc_status():
    """Get Traffic Control status"""
    try:
        tc_stats = pipeline.decision_engine.tc_controller.get_stats()
        return jsonify({
            "tc_initialized": pipeline.decision_engine.tc_controller.initialized,
            "interface": pipeline.decision_engine.tc_controller.interface,
            "stats": tc_stats
        }), 200
    except Exception as e:
        logger.error(f"TC status error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def reset_system():
    """Reset all TC rules and history"""
    try:
        pipeline.decision_engine.tc_controller.cleanup()
        pipeline.history.clear()
        pipeline.smoother.history.clear()
        pipeline.smoother.anomaly_counts.clear()
        pipeline.policy.overrides.clear()
        
        # Reinitialize TC
        pipeline.decision_engine.tc_controller.initialize_qdisc()
        
        return jsonify({"status": "success", "message": "System reset"}), 200
    except Exception as e:
        logger.error(f"Reset error: {e}")
        return jsonify({"error": str(e)}), 500


start_time = time.time()

if __name__ == "__main__":
    logger.info("=== ML WiFi Controller v2.0 STARTED ===")
    logger.info(f"Total bandwidth: {config.TOTAL_BANDWIDTH_MBPS} Mbps")
    logger.info(f"AP interface: {config.AP_INTERFACE}")
    logger.info(f"Processing interval: {config.PROCESSING_INTERVAL}s")
    logger.info(f"Frontend API enabled: /api/*")
    
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)