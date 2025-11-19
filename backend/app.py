from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from scapy.all import PcapReader, IP, IPv6, TCP, UDP

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_PRINT = 20
MAX_INSPECT = 3000
ALLOWED_EXT = {".pcap", ".pcapng", ".cap"}

def allowed_file(name):
    low = name.lower()
    return any(low.endswith(ext) for ext in ALLOWED_EXT)

def process_pcap(path):
    """Return short structured JSON summary."""
    summaries = []
    total = 0

    try:
        rdr = PcapReader(path)
    except Exception as e:
        return {"error": f"failed to read pcap: {e}"}

    for pkt in rdr:
        total += 1
        if len(summaries) < MAX_PRINT:
            length = len(pkt)
            src = dst = proto = "-"

            if IP in pkt:
                src = pkt[IP].src
                dst = pkt[IP].dst
                if TCP in pkt:
                    proto = f"TCP {pkt[TCP].sport}->{pkt[TCP].dport}"
                elif UDP in pkt:
                    proto = f"UDP {pkt[UDP].sport}->{pkt[UDP].dport}"
                else:
                    proto = f"IP proto={pkt[IP].proto}"

            elif IPv6 in pkt:
                src = pkt[IPv6].src
                dst = pkt[IPv6].dst
                proto = "IPv6"

            summaries.append({
                "len": length,
                "src": src,
                "dst": dst,
                "proto": proto
            })

        if total >= MAX_INSPECT:
            break

    rdr.close()

    return {
        "total_packets": total,
        "shown_packets": len(summaries),
        "packets": summaries
    }

@app.route("/traffic", methods=["POST"])
def traffic():
    # Case 1: multipart upload
    if "capture" in request.files:
        f = request.files["capture"]
        filename = secure_filename(f.filename or "capture.pcap")
        if not allowed_file(filename):
            filename += ".pcap"

        saved = os.path.join(UPLOAD_DIR, f"{datetime.utcnow().timestamp()}_{filename}")
        f.save(saved)
        summary = process_pcap(saved)
        return jsonify(summary), 200

    # Case 2: raw bytes upload
    data = request.get_data()
    if data:
        filename = request.headers.get("X-Filename", "capture.pcap")
        filename = secure_filename(filename)
        if not allowed_file(filename):
            filename += ".pcap"

        saved = os.path.join(UPLOAD_DIR, f"{datetime.utcnow().timestamp()}_{filename}")
        with open(saved, "wb") as fh:
            fh.write(data)

        summary = process_pcap(saved)
        return jsonify(summary), 200

    return jsonify({"error": "no pcap provided"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
