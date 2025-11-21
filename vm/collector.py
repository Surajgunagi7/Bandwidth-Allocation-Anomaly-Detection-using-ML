#!/usr/bin/env python3
"""
collector.py

Start tcpdump rotating pcaps every `--rotate-secs` seconds, watch the capture directory,
and upload each finished pcap to backend /traffic endpoint. Lightweight, single-worker
default for low-powered AP nodes.

"""

import argparse
import os
import subprocess
import threading
import time
import queue
import logging
import logging.handlers
import signal
import sys
import shutil
from pathlib import Path
from datetime import datetime
import math
import json

# Try requests, fallback to urllib
try:
    import requests
except Exception:
    requests = None
    import urllib.request
    import urllib.parse
    import mimetypes

# ---------- Defaults ----------
DEFAULT_ROTATE_SECS = 3
DEFAULT_BACKEND = "10.0.2.15:5000/traffic"
DEFAULT_CAPTURE_DIR = "/tmp/captures"
DEFAULT_LOG_FILE = "/tmp/collector.log"
DEFAULT_MAX_RETRIES = 5
DEFAULT_MAX_DISK_BYTES = 100 * 1024 * 1024  # 100 MB default
DEFAULT_MAX_FILES = 30  # fallback cap
WORKER_COUNT = 1  # low perf -> single uploader

# ---------- Helper functions ----------
def setup_logging(logfile, level=logging.INFO):
    logger = logging.getLogger("collector")
    logger.setLevel(level)
    handler = logging.handlers.RotatingFileHandler(logfile, maxBytes=2_000_000, backupCount=5)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # also log to stderr for interactive debugging
    stderr = logging.StreamHandler()
    stderr.setFormatter(formatter)
    logger.addHandler(stderr)
    return logger

def ensure_dirs(base_dir: Path):
    incoming = base_dir / "incoming"
    sent = base_dir / "sent"
    failed = base_dir / "failed"
    for d in (incoming, sent, failed):
        d.mkdir(parents=True, exist_ok=True)
    return incoming, sent, failed

def current_disk_usage_bytes(path: Path):
    total = 0
    for f in path.rglob('*'):
        if f.is_file():
            try:
                total += f.stat().st_size
            except Exception:
                pass
    return total

def file_count(path: Path):
    return sum(1 for _ in path.iterdir() if _.is_file())

def multipart_post_requests(url, file_path, meta=None, logger=None, timeout=30):
    """Send pcap via requests (if available). Returns (ok, status_or_exception)."""
    if requests is None:
        raise RuntimeError("requests module not available")
    with open(file_path, "rb") as fh:
        files = {"capture": (file_path.name, fh, "application/vnd.tcpdump.pcap")}
        data = {}
        if meta:
            # attach meta as JSON str
            data["meta"] = json.dumps(meta)
        try:
            r = requests.post(url, files=files, data=data, timeout=timeout)
            return (r.ok, f"{r.status_code} {r.reason}")
        except Exception as e:
            if logger: logger.debug("requests exception: %s", e)
            return (False, str(e))

def multipart_post_urllib(url, file_path, meta=None, timeout=30):
    """Fallback multipart POST with urllib (minimal)."""
    boundary = "----collectorboundary%f" % time.time()
    def encode_field(name, value):
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode()
    def encode_file(fieldname, filename, filebytes, content_type="application/octet-stream"):
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{fieldname}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
        return header + filebytes + b"\r\n"

    body_parts = []
    if meta:
        body_parts.append(encode_field("meta", json.dumps(meta)))
    with open(file_path, "rb") as fh:
        filebytes = fh.read()
    body_parts.append(encode_file("capture", os.path.basename(file_path), filebytes, "application/vnd.tcpdump.pcap"))
    body_parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(body_parts)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(body)))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (True, f"{resp.status} {resp.reason}")
    except Exception as e:
        return (False, str(e))

# ---------- Uploader worker ----------
class Uploader(threading.Thread):
    def __init__(self, q: queue.Queue, backend_url: str, sent_dir: Path, failed_dir: Path,
                 logger, ap_iface: str, max_retries=5, backoff_base=1.5, timeout=30):
        super().__init__(daemon=True)
        self.q = q
        self.backend = backend_url
        self.sent_dir = sent_dir
        self.failed_dir = failed_dir
        self.logger = logger
        self.ap_iface = ap_iface
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        self.logger.info("Uploader started")
        while not self._stop.is_set():
            try:
                filepath = self.q.get(timeout=1.0)
            except queue.Empty:
                continue
            if not filepath.exists():
                self.logger.warning("File disappeared before upload: %s", filepath)
                self.q.task_done()
                continue

            meta = {"ap_iface": self.ap_iface, "filename": filepath.name, "ts": filepath.stat().st_mtime}
            success = False
            attempt = 0
            while attempt <= self.max_retries and not success:
                attempt += 1
                try:
                    if requests:
                        ok, info = multipart_post_requests(self.backend, filepath, meta=meta, logger=self.logger, timeout=self.timeout)
                    else:
                        ok, info = multipart_post_urllib(self.backend, filepath, meta=meta, timeout=self.timeout)
                except Exception as e:
                    ok = False
                    info = str(e)
                if ok:
                    success = True
                    # move file to sent
                    dest = self.sent_dir / filepath.name
                    try:
                        shutil.move(str(filepath), str(dest))
                    except Exception as e:
                        self.logger.exception("Failed to move to sent: %s", e)
                    self.logger.info("Uploaded %s -> backend OK (attempt %d): %s", filepath.name, attempt, info)
                else:
                    # retry with exponential backoff
                    self.logger.warning("Upload failed for %s (attempt %d/%d): %s", filepath.name, attempt, self.max_retries, info)
                    self.logger.debug("Failure detail: %s", info)
                    if attempt > self.max_retries:
                        # move to failed
                        dest = self.failed_dir / filepath.name
                        try:
                            shutil.move(str(filepath), str(dest))
                        except Exception as e:
                            self.logger.exception("Failed to move to failed: %s", e)
                        self.logger.error("Moved %s to failed after %d attempts", filepath.name, attempt-1)
                        break
                    sleep_for = (self.backoff_base ** attempt) + (attempt * 0.1)
                    time.sleep(min(sleep_for, 30))
            self.q.task_done()
        self.logger.info("Uploader stopped")

# ---------- Main script ----------
def start_tcpdump(iface: str, capture_pattern: str, rotate_secs: int, logger, use_sudo=True):
    # Build tcpdump command. We rely on tcpdump's -G rotation and strftime expansion in the filename.
    # capture_pattern should include strftime tokens like %Y%m%dT%H%M%S
    cmd = []
    if use_sudo:
        cmd.append("sudo")
    cmd.extend([
        "tcpdump",
        "-i", iface,
        "-s", "0",  # capture full packet
        "-w", capture_pattern,
        "-G", str(rotate_secs),
        "-Z", "root",  # Drop privileges to root (helps with sudo)
    ])
    logger.info("Starting tcpdump: %s", " ".join(cmd))
    # Start as subprocess; let it run in background. We'll not capture stdout/stderr to reduce IO.
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc

def watchdog_loop(incoming: Path, q: queue.Queue, logger, poll_interval=1.0, rotate_secs=3):
    """
    Polls the incoming directory for new files. To avoid racing with tcpdump writing the file,
    we consider files older than rotate_secs and stable (size not changing) as finished and enqueue them.
    """
    logger.info("Watchdog watching %s", incoming)
    seen = set()
    while not stop_event.is_set():
        try:
            for f in incoming.iterdir():
                if not f.is_file():
                    continue
                if f.name in seen:
                    continue
                # ensure file is stable (size not changing)
                try:
                    size1 = f.stat().st_size
                    mtime1 = f.stat().st_mtime
                except Exception:
                    continue
                
                # Wait a bit to check stability
                time.sleep(max(0.2, min(1.0, rotate_secs / 3)))
                
                try:
                    size2 = f.stat().st_size
                    mtime2 = f.stat().st_mtime
                except Exception:
                    continue
                
                # If size unchanged and file is old enough, enqueue it
                age = time.time() - mtime2
                if size1 == size2 and mtime1 == mtime2 and age >= (rotate_secs * 0.8):
                    logger.debug("Enqueueing %s (size=%d, age=%.1fs)", f.name, size2, age)
                    q.put(f)
                    seen.add(f.name)
            time.sleep(poll_interval)
        except Exception as e:
            logger.exception("Watchdog error: %s", e)
            time.sleep(1.0)

def enforce_retention(incoming: Path, sent: Path, failed: Path, max_bytes: int, max_files: int, logger):
    """
    Ensure total usage across incoming+sent+failed stays under max_bytes and max_files.
    Delete oldest files in sent first, then failed, then incoming (should be rare).
    """
    all_dirs = [sent, failed, incoming]
    # build list of (path, mtime)
    files = []
    for d in all_dirs:
        for f in d.iterdir():
            if f.is_file():
                try:
                    files.append((f, f.stat().st_mtime))
                except Exception:
                    pass
    # sort oldest first
    files.sort(key=lambda x: x[1])
    total_bytes = sum(f.stat().st_size for f, _ in files if f.exists())
    total_files = len(files)
    logger.debug("Retention check: %d files, %.2fMB", total_files, total_bytes / (1024*1024))
    while (total_bytes > max_bytes or total_files > max_files) and files:
        f, _ = files.pop(0)
        try:
            size = f.stat().st_size
            logger.warning("Removing old file %s to respect retention (size %.2f KB)", f, size/1024)
            f.unlink()
            total_bytes -= size
            total_files -= 1
        except Exception as e:
            logger.exception("Failed removing file %s: %s", f, e)
            break

# ---------- Argument parsing ----------
parser = argparse.ArgumentParser(description="Lightweight tcpdump collector + uploader")
parser.add_argument("--iface", required=True, help="AP interface to capture (e.g. ap1-wlan1)")
parser.add_argument("--capture-dir", default=DEFAULT_CAPTURE_DIR, help="Base directory for captures")
parser.add_argument("--backend", default=DEFAULT_BACKEND, help="/traffic backend URL")
parser.add_argument("--rotate-secs", type=int, default=DEFAULT_ROTATE_SECS, help="tcpdump rotate seconds")
parser.add_argument("--log-file", default=DEFAULT_LOG_FILE, help="path to log file")
parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="upload retry count")
parser.add_argument("--max-disk-bytes", type=int, default=DEFAULT_MAX_DISK_BYTES, help="max bytes for retention")
parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, help="max number of files to keep")
parser.add_argument("--worker-count", type=int, default=WORKER_COUNT, help="uploader worker threads (low perf -> 1)")
parser.add_argument("--no-sudo", action="store_true", help="Don't prefix tcpdump with sudo (if unnecessary)")

# ---------- Global stop event ----------
stop_event = threading.Event()
logger = None

def signal_handler(signum, frame):
    if logger:
        logger.info("Received signal %s, shutting down...", signum)
    stop_event.set()

# ---------- main execution ----------
if __name__ == "__main__":
    args = parser.parse_args()
    
    # setup logging early
    logger = setup_logging(args.log_file)
    
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, signal_handler)

    base_dir = Path(args.capture_dir)
    incoming_dir, sent_dir, failed_dir = ensure_dirs(base_dir)
    logger.info("Capture base dir: %s (incoming=%s)", base_dir, incoming_dir)

    # build capture pattern: we'll write into incoming dir with strftime pattern
    pattern = str(incoming_dir / "cap-%Y%m%dT%H%M%S.pcap")

    # Start tcpdump subprocess (we rely on tcpdump supporting -G rotation with strftime)
    try:
        tcpdump_proc = start_tcpdump(args.iface, pattern, args.rotate_secs, logger, use_sudo=not args.no_sudo)
    except Exception as e:
        logger.exception("Failed to start tcpdump: %s", e)
        sys.exit(1)

    # Give tcpdump a moment to start
    time.sleep(1)

    # Prepare queue and workers
    q = queue.Queue()
    uploaders = []
    for i in range(max(1, args.worker_count)):
        u = Uploader(q, args.backend, sent_dir, failed_dir, logger,
                     ap_iface=args.iface, max_retries=args.max_retries)
        u.start()
        uploaders.append(u)

    # Start watchdog thread
    wd_thread = threading.Thread(target=watchdog_loop, args=(incoming_dir, q, logger, 1.0, args.rotate_secs), daemon=True)
    wd_thread.start()

    # Main loop enforces retention periodically
    try:
        logger.info("Collector running. Press Ctrl+C to stop.")
        while not stop_event.is_set():
            enforce_retention(incoming_dir, sent_dir, failed_dir, args.max_disk_bytes, args.max_files, logger)
            time.sleep(5)
    except KeyboardInterrupt:
        stop_event.set()

    # shutdown sequence
    logger.info("Shutting down: stopping tcpdump")
    try:
        tcpdump_proc.terminate()
        try:
            tcpdump_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            tcpdump_proc.kill()
    except Exception as e:
        logger.debug("tcpdump stop error: %s", e)

    logger.info("Waiting for uploader queue to drain")
    q.join()  # wait for all queued uploads to finish (or time out via uploader)
    for u in uploaders:
        u.stop()
        u.join(timeout=2)

    logger.info("Collector exited cleanly")