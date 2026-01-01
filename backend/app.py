#!/usr/bin/env python3
"""
Flask Backend with Improved Logging and Dynamic Bandwidth API
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

from config import Config
from ml_integration import PipelineController
    
app = Flask(__name__)
CORS(app)
app.secret_key = Config.SECRET_KEY
start_time = time.time()

logger = logging.getLogger(__name__)

# Initialize pipeline
pipeline = PipelineController(
    models_dir=str(Config.MODELS_DIR),
    interface=Config.AP_INTERFACE,
    update_interval=Config.TC_UPDATE_INTERVAL
)

worker_thread = None
worker_lock = threading.Lock()
worker_restart_count = 0
last_worker_restart = None
file_lock = threading.Lock()
pipeline_lock = threading.RLock()


def pcap_processing_worker():
    """Background worker for PCAP processing"""
    logger.info("🔄 Background worker started")
    processed_files = {}
    FILE_STABLE_TIME = 2.0
    MAX_FILES_PER_BATCH = 5
    CLEANUP_THRESHOLD = 500
    
    while True:
        try:
            with file_lock:
                try:
                    pcap_files = list(Config.UPLOAD_DIR.glob("*.pcap*"))
                except Exception as e:
                    logger.error(f"Error listing uploads: {e}")
                    time.sleep(Config.PROCESSING_INTERVAL)
                    continue
                
                new_files = []
                current_time = time.time()
                
                for pcap_file in pcap_files:
                    try:
                        if not pcap_file.exists():
                            continue
                        
                        file_stat = pcap_file.stat()
                        file_id = (file_stat.st_size, file_stat.st_mtime)
                        
                        if file_id in processed_files:
                            continue
                        
                        file_age = current_time - file_stat.st_mtime
                        
                        if file_age >= FILE_STABLE_TIME and file_stat.st_size > 0:
                            new_files.append((pcap_file, file_stat.st_size))
                    except Exception as e:
                        logger.debug(f"Cannot stat {pcap_file.name}: {e}")
                        continue
                
                new_files.sort(key=lambda x: x[1])
                files_to_process = new_files[:MAX_FILES_PER_BATCH]
                
                if files_to_process:
                    logger.info(f"📦 Processing batch: {len(files_to_process)} file(s)")
            
            for pcap_file, file_size in files_to_process:
                try:
                    if not pcap_file.exists():
                        continue
                    
                    logger.info(f"Processing: {pcap_file.name} ({file_size} bytes)")
                    
                    with pipeline_lock:
                        result = pipeline.process_pcap(str(pcap_file.absolute()))
                    
                    with file_lock:
                        if not pcap_file.exists():
                            continue
                        
                        file_stat = pcap_file.stat()
                        file_id = (file_stat.st_size, file_stat.st_mtime)
                        
                        if result.get("status") == "success":
                            dest = Config.PROCESSED_DIR / pcap_file.name
                            counter = 1
                            original_dest = dest
                            while dest.exists():
                                dest = Config.PROCESSED_DIR / f"{original_dest.stem}_{counter}{original_dest.suffix}"
                                counter += 1
                            
                            try:
                                shutil.move(str(pcap_file), str(dest))
                                logger.info(f"✅ Moved: {pcap_file.name}")
                            except Exception as move_error:
                                logger.error(f"Move failed: {move_error}")
                        else:
                            error_dir = Config.UPLOAD_DIR.parent / "errors"
                            error_dir.mkdir(exist_ok=True)
                            error_dest = error_dir / f"error_{pcap_file.name}"
                            try:
                                if pcap_file.exists():
                                    shutil.move(str(pcap_file), str(error_dest))
                            except Exception as e:
                                logger.debug(f"Error move failed: {e}")
                        
                        processed_files[file_id] = current_time
                    
                except Exception as e:
                    logger.error(f"Processing error for {pcap_file.name}: {e}")
                    with file_lock:
                        try:
                            file_stat = pcap_file.stat()
                            file_id = (file_stat.st_size, file_stat.st_mtime)
                            processed_files[file_id] = current_time
                        except:
                            pass
            
            with file_lock:
                if len(processed_files) > CLEANUP_THRESHOLD:
                    sorted_items = sorted(processed_files.items(), key=lambda x: x[1], reverse=True)
                    processed_files = dict(sorted_items[:CLEANUP_THRESHOLD // 2])
            
            time.sleep(Config.PROCESSING_INTERVAL)

        except Exception as e:
            logger.error(f"Worker crashed: {e}", exc_info=True)
            time.sleep(5)


def start_worker():
    """Start background worker"""
    global worker_thread, worker_restart_count, last_worker_restart

    with worker_lock:
        if worker_thread and worker_thread.is_alive():
            return

        worker_thread = threading.Thread(
            target=pcap_processing_worker,
            daemon=True,
            name="pcap-worker"
        )
        worker_thread.start()

        worker_restart_count += 1
        last_worker_restart = time.time()

        logger.info(f"Worker started (restart #{worker_restart_count})")


def worker_supervisor():
    """Supervisor to ensure worker is always running"""
    backoff = 2
    max_backoff = 60

    while True:
        try:
            with worker_lock:
                alive = worker_thread and worker_thread.is_alive()

            if not alive:
                logger.error("Worker not alive, restarting")
                start_worker()
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
            else:
                backoff = 2

            time.sleep(3)

        except Exception as e:
            logger.error(f"Supervisor crash: {e}", exc_info=True)
            time.sleep(5)


# Start worker and supervisor
start_worker()
supervisor_thread = threading.Thread(
    target=worker_supervisor,
    daemon=True,
    name="worker-supervisor"
)
supervisor_thread.start()


def generate_filename(original_filename):
    """Generate timestamped filename"""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    secure_name = secure_filename(original_filename or "capture.pcap")
    if not any(secure_name.lower().endswith(ext) for ext in Config.ALLOWED_EXTENSIONS):
        secure_name += ".pcap"
    return f"{timestamp}_{secure_name}"



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
            
            if request.content_length and request.content_length > Config.MAX_FILE_SIZE:
                return jsonify({"error": "File too large"}), 413
            
            filename = generate_filename(file.filename)
            saved_path = Config.UPLOAD_DIR / filename
            
            with file_lock:
                file.save(str(saved_path))
            
            logger.info(f"Upload saved: {filename}")
        
        elif request.data:
            data = request.get_data()
            if len(data) > Config.MAX_FILE_SIZE:
                return jsonify({"error": "File too large"}), 413
            
            filename = request.headers.get("X-Filename", "capture.pcap")
            filename = generate_filename(filename)
            saved_path = Config.UPLOAD_DIR / filename
            
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
        with pipeline_lock:
            pipeline_stats = pipeline.get_statistics()
        
        with file_lock:
            uploads_pending = len(list(Config.UPLOAD_DIR.glob("*.pcap*")))
            processed_total = len(list(Config.PROCESSED_DIR.glob("*.pcap*")))
            error_dir = Config.UPLOAD_DIR.parent / "errors"
            errors_total = len(list(error_dir.glob("*.pcap*"))) if error_dir.exists() else 0
        
        return jsonify({
            "total_bandwidth_mbps": Config.get_total_bandwidth(),
            "ap_interface": Config.AP_INTERFACE,
            "active_devices": pipeline_stats.get("active_devices", 0),
            "uploads_pending": uploads_pending,
            "processed_total": processed_total,
            "errors_total": errors_total,
            "uptime": time.time() - start_time,
            "worker_alive": worker_thread.is_alive() if worker_thread else False,
            "policy_mode": pipeline_stats.get("policy_mode", "auto"),
            "active_overrides": pipeline_stats.get("active_overrides", 0)
        })
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": "Stats failed"}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy" if worker_thread and worker_thread.is_alive() else "worker_dead",
        "worker_alive": worker_thread.is_alive() if worker_thread else False,
        "restart_count": worker_restart_count,
        "last_restart": last_worker_restart
    }), 200


@app.route("/api/bandwidth/config", methods=["GET", "POST"])
def bandwidth_config():
    """Get or set bandwidth configuration"""
    if request.method == "GET":
        return jsonify({
            "total_bandwidth_mbps": Config.get_total_bandwidth(),
            "interface": Config.AP_INTERFACE,
            "source": "manual" if Config._total_bandwidth_mbps else "detected"
        }), 200
    
    elif request.method == "POST":
        try:
            data = request.get_json()
            bandwidth_mbps = data.get('bandwidth_mbps')
            
            if not bandwidth_mbps or bandwidth_mbps <= 0:
                return jsonify({"error": "Invalid bandwidth value"}), 400
            
            Config.set_total_bandwidth(int(bandwidth_mbps))
            
            # Reinitialize TC with new bandwidth
            with pipeline_lock:
                pipeline.decision_engine.tc_controller.initialize_qdisc(int(bandwidth_mbps))
            
            logger.info(f"✅ Bandwidth updated to {bandwidth_mbps} Mbps")
            
            return jsonify({
                "status": "success",
                "bandwidth_mbps": int(bandwidth_mbps)
            }), 200
            
        except Exception as e:
            logger.error(f"Bandwidth config error: {e}")
            return jsonify({"error": str(e)}), 500


@app.route("/api/devices", methods=["GET"])
def get_devices():
    """Get all active device allocations"""
    try:
        with pipeline_lock:
            stats = pipeline.get_statistics()
            devices = stats.get("allocations", [])
            history_snapshot = list(pipeline.history)

        if history_snapshot:
            last_entry = history_snapshot[-1]
            pred_map = {}
            
            # Try to get from final predictions
            if 'final' in last_entry:
                pred_map = {p['mac_address']: p for p in last_entry['final']}
            elif 'predictions' in last_entry:
                pred_map = {p['mac_address']: p for p in last_entry['predictions']}
            
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

        with pipeline_lock:
            history_snapshot = list(pipeline.history[-10:])

        for entry in history_snapshot:
            timestamp = entry['timestamp']
            predictions = entry.get('final', entry.get('predictions', []))
            
            for pred in predictions:
                if pred.get('is_anomaly', False):
                    anomalies.append({
                        'mac_address': pred['mac_address'],
                        'timestamp': timestamp,
                        'anomaly_score': pred.get('anomaly_score', 0.0),
                        'traffic_class': pred.get('traffic_class', 'unknown'),
                        'bandwidth_kbps': pred.get('predicted_bandwidth_kbps', 0)
                    })
        
        anomalies.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({"anomalies": anomalies[:20]}), 200
    except Exception as e:
        logger.error(f"Get anomalies error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/history", methods=["GET"])
def get_history():
    """Get prediction history with enforced bandwidth alignment"""
    try:
        limit = int(request.args.get("limit", 10))

        with pipeline_lock:
            history = list(pipeline.history[-limit:])

            enforced_map = {
                mac: alloc.allocated_bw_kbps
                for mac, alloc in pipeline.decision_engine.tc_controller.active_allocations.items()
            }

        if history:
            latest = history[-1]

            if "final" in latest:
                for item in latest["final"]:
                    mac = item.get("mac_address")

                    if mac in enforced_map:
                        item["enforced_bandwidth_kbps"] = enforced_map[mac]
                    else:
                        item["enforced_bandwidth_kbps"] = item.get(
                            "predicted_bandwidth_kbps", 0
                        )

        return jsonify({"history": history}), 200

    except Exception as e:
        logger.error(f"Get history error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/policy/mode", methods=["POST"])
def set_policy_mode():
    """Set global bandwidth mode"""
    try:
        data = request.get_json()
        mode = data.get('mode', 'auto')
        
        if mode not in ['auto', 'equal', 'manual']:
            return jsonify({"error": "Invalid mode"}), 400
        
        with pipeline_lock:
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
        
        with pipeline_lock:
            pipeline.set_device_override(mac, bandwidth_kbps, priority, duration_sec)
        
        return jsonify({"status": "success", "mac": mac}), 200
    except Exception as e:
        logger.error(f"Override error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/policy/override/<mac_address>", methods=["DELETE"])
def clear_device_override(mac_address):
    """Clear manual override"""
    try:
        with pipeline_lock:
            pipeline.clear_device_override(mac_address)
        return jsonify({"status": "success", "mac": mac_address}), 200
    except Exception as e:
        logger.error(f"Clear override error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/tc/status", methods=["GET"])
def get_tc_status():
    """Get Traffic Control status"""
    try:
        with pipeline_lock:
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
        with pipeline_lock:
            pipeline.history.clear()
            pipeline.smoother.history.clear()
            pipeline.smoother.anomaly_counts.clear()
            pipeline.policy.overrides.clear()
            pipeline.decision_engine.tc_controller.cleanup()
            pipeline.decision_engine.tc_controller.initialize_qdisc()
        
        logger.info("System reset complete")
        
        return jsonify({"status": "success", "message": "System reset"}), 200
    except Exception as e:
        logger.error(f"Reset error: {e}")
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("ML WiFi Controller v2.0 STARTED")
    logger.info("=" * 60)
    logger.info(f"Total bandwidth: {Config.get_total_bandwidth()} Mbps")
    logger.info(f"AP interface: {Config.AP_INTERFACE}")
    logger.info(f"Processing interval: {Config.PROCESSING_INTERVAL}s")
    logger.info(f"Logs directory: {Config.LOGS_DIR}")
    logger.info("=" * 60)
    
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)