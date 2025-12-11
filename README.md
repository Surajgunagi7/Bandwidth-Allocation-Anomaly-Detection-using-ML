# Backend Architecture - Detailed Explanation

## 📋 Overview

The backend system implements a machine learning-powered WiFi bandwidth allocation and anomaly detection system. The architecture follows a **pipeline pattern**: `PCAP Upload → Feature Extraction → ML Inference → Bandwidth Enforcement`.

---

## 🏗️ System Architecture Diagram

```
┌─────────────────┐
│   app.py        │  (Flask web server & file upload handler)
│                 │
│  ┌────────────┐ │
│  │ /traffic   │ │  Receives PCAP files
│  │ /stats     │ │  Returns statistics
│  │ /health    │ │  Health check endpoint
│  └────────────┘ │
│                 │
│  pcap_processing_worker (background thread)
│  - Monitors uploads/ folder
│  - Calls pipeline.process_pcap()
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│   ml_integration.py                     │  (Main ML pipeline orchestrator)
│   PipelineController                    │
│                                         │
│  process_pcap(pcap_path)               │
│  ├─> Step 1: Extract Features          │
│  ├─> Step 2: Predict Bandwidth         │
│  ├─> Step 3: Detect Anomalies          │
│  ├─> Step 4: Classify Traffic          │
│  ├─> Step 5: Merge Predictions         │
│  ├─> Step 6: Enforce Allocations       │
│  └─> Step 7: Store History             │
└────────┬────────────────────────────────┘
         │
    ┌────┴───────┬──────────────┬────────────────┐
    │            │              │                │
    ▼            ▼              ▼                ▼
┌─────────┐ ┌─────────┐ ┌─────────────┐ ┌──────────────────┐
│feature_ │ │ml_      │ │config.py    │ │bandwidth_        │
│extractor│ │models   │ │Config       │ │enforcer.py       │
│.py      │ │(joblib) │ │             │ │                  │
│         │ │         │ │ MODELS_DIR  │ │ BandwidthDecision│
│ Extract │ │ ┌─────┐ │ │ AP_INTERFACE│ │ Engine           │
│ Features│ │ │BW   │ │ │ TOTAL_BW_MB │ │                  │
│ from    │ │ │Pred │ │ │ ANOMALY_CAP │ │ Apply TC rules   │
│ PCAP    │ │ │     │ │ └─────────────┘ │                  │
│         │ │ ├─────┤ │                  │ TrafficController│
└─────────┘ │ │Anom  │ │                  │                  │
            │ │Detect│ │                  │ - initialize_    │
            │ ├─────┤ │                  │   qdisc()        │
            │ │Scaler│ │                  │ - apply_         │
            │ │(s)   │ │                  │   allocation()   │
            │ └─────┘ │                  │ - cleanup()      │
            └─────────┘                  └──────────────────┘
                                                  ▲
                                                  │
                                         Linux TC (Traffic Control)
                                         on AP interface
```

---

## 📁 File Interactions in Detail

### 1️⃣ **config.py** - Central Configuration Hub

**Purpose:** Centralized configuration for all modules

**Key Variables:**
```python
BASE_DIR                 # Root backend directory
UPLOAD_DIR              # Where PCAP files are uploaded
PROCESSED_DIR           # Where processed PCAPs are moved
LOGS_DIR                # Logging directory
MODELS_DIR              # ML models location
TOTAL_BANDWIDTH_MBPS    # Total available bandwidth (default: 100 Mbps)
AP_INTERFACE            # Network interface name (default: ap1-wlan1)
ALLOWED_EXTENSIONS      # {".pcap", ".pcapng", ".cap"}
MAX_FILE_SIZE           # 50 MB
PROCESSING_INTERVAL     # Check for new PCAPs every N seconds (default: 5)
ANOMALY_BANDWIDTH_CAP   # Max bandwidth for anomalous traffic (default: 1000 kbps)
```

**Used By:**
- **app.py** - Reads configuration for Flask server
- **ml_integration.py** - Passes to PipelineController
- **feature_extractor.py** - Gets KNOWN_AP_MACS to skip AP's own traffic
- **bandwidth_enforcer.py** - Gets TOTAL_BANDWIDTH_MBPS

---

### 2️⃣ **feature_extractor.py** - PCAP Feature Extraction

**Purpose:** Convert raw PCAP packets into ML-ready feature vectors

**Main Classes:**

#### `FlowKey` (Internal)
- Represents a unique network flow
- Groups packets by: source MAC, destination MAC, source IP, destination IP, protocol

#### `FlowFeatures` (Internal)
- Stores raw packet data for a flow
- Tracks: packet_sizes, timestamps, tcp_flags, port numbers, protocols, bytes, packets

#### `PCAPFeatureExtractor`
**Key Methods:**

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `extract_from_pcap()` | PCAP file path | DataFrame with features per MAC | Read PCAP, process packets, compute features |
| `_process_packets()` | Packet list | Populates self.flows dict | Parse each packet, extract metadata |
| `_compute_features()` | self.flows | DataFrame | Calculate 21+ ML features per MAC |
| `_aggregate_by_mac()` | DataFrame | Aggregated DataFrame | Combine multiple flows from same MAC |
| `_calculate_entropy()` | Packet sizes array | Float entropy value | Measure randomness in packet sizes |
| `get_bandwidth_features()` | Full features DF | Subset DF | Return only 16 features for bandwidth model |
| `get_anomaly_features()` | Full features DF | Full DF | Return all features for anomaly model |

**Entry Point Function:**
```python
process_pcap_file(pcap_path, output_csv=None) → Dict
```
Returns:
```python
{
    'bandwidth': DataFrame,   # 16 features for bandwidth prediction
    'anomaly': DataFrame,     # All features for anomaly detection
    'all': DataFrame          # Full feature set (21 features)
}
```

**Features Generated (21 total):**
- **Temporal:** flow_duration, bytes_per_second, packets_per_second, avg_inter_arrival_time
- **Packet Stats:** avg_packet_size, std_packet_size, packet_size_variance, total_bytes, total_packets
- **Protocol:** protocol_type, protocol_diversity
- **Port:** unique_dst_ports, unique_src_ports
- **Encryption:** is_encrypted (based on common encrypted ports: 443, 993, etc.)
- **TCP Flags:** tcp_flag_ratio
- **Entropy:** payload_entropy (randomness in packet sizes)
- **Bidirectional:** bidirectional_ratio
- **Time:** time_of_day
- **Anomaly Indicators:** connection_rate, failed_connection_ratio, port_scan_indicator

**Example Output:**
```
mac_address         total_bytes  bytes_per_second  protocol_type  is_encrypted
00:11:22:33:44:55   50000        1234.5           1 (TCP)        1 (HTTPS)
00:11:22:33:44:66   25000        456.2            2 (UDP)        0 (HTTP)
```

---

### 3️⃣ **ml_integration.py** - ML Pipeline Orchestrator

**Purpose:** Coordinate feature extraction → ML prediction → enforcement

**Main Classes:**

#### `MLModelManager`
Manages loading and running ML models

**Key Methods:**

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `_load_models()` | None | Loads 4 joblib files | Load trained models and scalers from disk |
| `predict_bandwidth()` | Features DF | Predictions DF | Predict bandwidth requirement (in kbps) |
| `detect_anomalies()` | Features DF | Predictions DF | Detect anomalous traffic patterns |
| `classify_traffic()` | Features DF | Classification DF | Classify as video/voip/bulk/etc |

**Models Loaded:**
```
models/
├── bandwidth_predictor.pkl      → Predicts bandwidth in kbps
├── anomaly_detector.pkl         → Isolation Forest for anomaly detection
├── bandwidth_scaler.pkl         → Feature scaler for bandwidth model
└── anomaly_scaler.pkl           → Feature scaler for anomaly model
```

**Return Examples:**

`predict_bandwidth()` Returns:
```
mac_address         predicted_bandwidth_kbps
00:11:22:33:44:55   5000 (5 Mbps)
00:11:22:33:44:66   2000 (2 Mbps)
```

`detect_anomalies()` Returns:
```
mac_address         is_anomaly  anomaly_score
00:11:22:33:44:55   False       0.15
00:11:22:33:44:66   True        0.85  (higher = more anomalous)
```

`classify_traffic()` Returns:
```
mac_address         traffic_class
00:11:22:33:44:55   video_conference
00:11:22:33:44:66   web
```

---

#### `PipelineController` - Main Orchestrator
**Coordinates entire pipeline**

**Constructor:**
```python
PipelineController(models_dir, interface, update_interval)
├── Creates MLModelManager
├── Creates BandwidthDecisionEngine
└── Initializes empty history list
```

**Key Method: `process_pcap(pcap_path) → Dict`**

**Execution Flow:**

```
┌─ Step 1: Extract Features ─────────────────────┐
│ process_pcap_file(pcap_path)                   │
│ ↓                                               │
│ Returns: {                                      │
│   'bandwidth': 16-feature DataFrame,            │
│   'anomaly': 21-feature DataFrame,              │
│   'all': 21-feature DataFrame                   │
│ }                                               │
└────────────────────────────────────────────────┘
         ↓
┌─ Step 2: Run ML Predictions ──────────────────┐
│ bandwidth_pred = predict_bandwidth(all_df)     │
│ ↓                                               │
│ Returns: {mac_address, predicted_bw_kbps}      │
│                                                 │
│ anomaly_pred = detect_anomalies(all_df)        │
│ ↓                                               │
│ Returns: {mac_address, is_anomaly, score}      │
│                                                 │
│ traffic_class = classify_traffic(all_df)       │
│ ↓                                               │
│ Returns: {mac_address, traffic_class}          │
└────────────────────────────────────────────────┘
         ↓
┌─ Step 3: Merge Predictions ───────────────────┐
│ merged = _merge_predictions(                   │
│   features, bandwidth_pred,                    │
│   anomaly_pred, traffic_class                  │
│ )                                               │
│ ↓                                               │
│ Returns single DataFrame with all columns      │
└────────────────────────────────────────────────┘
         ↓
┌─ Step 4: Enforce Bandwidth ───────────────────┐
│ enforcement = _enforce_allocations(merged)     │
│ ↓                                               │
│ Calls: decision_engine.process_ml_predictions()│
│ ↓                                               │
│ Returns: {status, devices_updated, active}     │
└────────────────────────────────────────────────┘
         ↓
┌─ Step 5: Store History ───────────────────────┐
│ _update_history(merged)                        │
│ Appends to self.history (max 10 entries)       │
└────────────────────────────────────────────────┘
         ↓
┌─ Step 6: Return Response ─────────────────────┐
│ {                                               │
│   'status': 'success',                          │
│   'timestamp': ISO8601 timestamp,               │
│   'devices_processed': 5,                       │
│   'anomalies_detected': 1,                      │
│   'predictions': [list of dicts],               │
│   'enforcement': enforcement result             │
│ }                                               │
└────────────────────────────────────────────────┘
```

**Success Response Example:**
```json
{
  "status": "success",
  "timestamp": "2025-12-11T10:30:45.123456",
  "devices_processed": 3,
  "anomalies_detected": 1,
  "predictions": [
    {
      "mac_address": "00:11:22:33:44:55",
      "predicted_bandwidth_kbps": 5000,
      "is_anomaly": false,
      "anomaly_score": 0.15,
      "traffic_class": "video_conference"
    },
    {
      "mac_address": "00:11:22:33:44:66",
      "predicted_bandwidth_kbps": 2000,
      "is_anomaly": false,
      "anomaly_score": 0.20,
      "traffic_class": "web"
    },
    {
      "mac_address": "00:11:22:33:44:77",
      "predicted_bandwidth_kbps": 10000,
      "is_anomaly": true,
      "anomaly_score": 0.85,
      "traffic_class": "bulk"
    }
  ],
  "enforcement": {
    "status": "enforced",
    "devices_updated": 3,
    "active_allocations": 3
  }
}
```

**Failure Response Example:**
```json
{
  "status": "error",
  "message": "Failed to load PCAP file: corrupted file"
}
```

**Other Methods:**
- `get_statistics()` → Returns active devices, allocations, TC stats, history count

---

### 4️⃣ **bandwidth_enforcer.py** - Network Traffic Control

**Purpose:** Apply ML predictions to Linux kernel traffic shaping

**Main Classes:**

#### `BandwidthAllocation` (Data Class)
Represents one device's bandwidth allocation:
```python
@dataclass
class BandwidthAllocation:
    mac_address: str           # e.g., "00:11:22:33:44:55"
    allocated_bw_kbps: int     # e.g., 5000 kbps = 5 Mbps
    priority: int              # 1 (high), 2 (medium), 3 (low)
    device_ip: Optional[str]   # e.g., "10.0.0.2"
```

---

#### `TrafficController`
Manages Linux TC (Traffic Control) HTB (Hierarchical Token Bucket) commands

**Key Methods:**

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `initialize_qdisc()` | Total bandwidth (Mbps) | Sets up HTB root | Create traffic control structure |
| `apply_allocation()` | BandwidthAllocation | Linux TC commands | Apply bandwidth limit to device |
| `remove_allocation()` | MAC address | Linux TC commands | Remove device's bandwidth limit |
| `get_stats()` | None | Raw TC statistics | Query current traffic shaping stats |
| `cleanup()` | None | Removes all TC config | Reset interface to default |

**HTB Hierarchy Created:**
```
Root (handle 1:)
├── High Priority (1:10)      → 50% of total bandwidth
├── Medium Priority (1:20)    → 30% of total bandwidth
└── Low Priority (1:30)       → 20% of total bandwidth
    ├── Device 1 (1:10X)      → Allocated rate
    ├── Device 2 (1:20Y)      → Allocated rate
    └── Device 3 (1:30Z)      → Allocated rate
```

**Example: apply_allocation() Execution**

For device with MAC `00:11:22:33:44:55`, 5000 kbps, priority 1:

```bash
# 1. Calculate handle (hash of MAC)
handle = 1:10155  # (100 + hash % 10000)

# 2. Add class under high-priority parent (1:10)
tc class add dev ap1-wlan1 parent 1:10 classid 1:10155 \
  htb rate 5000kbit ceil 10000kbit

# 3. Add filter for upload (match source MAC)
tc filter add dev ap1-wlan1 protocol ip parent 1: \
  prio 1 u32 match ether src 00:11:22:33:44:55 flowid 1:10155

# 4. Add filter for download (match destination MAC)
tc filter add dev ap1-wlan1 protocol ip parent 1: \
  prio 1 u32 match ether dst 00:11:22:33:44:55 flowid 1:10155
```

**Result:** Device limited to 5 Mbps, can burst to 10 Mbps

---

#### `BandwidthDecisionEngine`
High-level controller connecting ML predictions to TC enforcement

**Key Methods:**

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `process_ml_predictions()` | List[Dict] predictions | None | Process predictions and enforce via TC |
| `should_update()` | Old & new allocation | Boolean | Decide if update needed (threshold check) |
| `_classify_priority()` | traffic_class, is_anomaly | 1, 2, or 3 | Map traffic type to priority |
| `detect_ap_mac()` | None | AP MAC string | Detect AP's own MAC, skip from shaping |

**Priority Assignment Logic:**

```python
if is_anomaly:
    priority = 3  # Lowest - rate limit anomalous traffic
else:
    priority_map = {
        'voip': 1,                 # High
        'video_conference': 1,     # High
        'video': 1,                # High
        'streaming': 2,            # Medium
        'web': 2,                  # Medium
        'bulk': 3,                 # Low
        'file_transfer': 3,        # Low
        'unknown': 2,              # Medium (default)
    }
```

**Change Threshold Logic:**
```python
def should_update(old_alloc, new_alloc):
    change = |new_bw - old_bw| / old_bw
    
    return (change >= 0.15) OR (priority changed)
    # Only update if 15%+ bandwidth change OR priority change
    # Prevents constant fluctuation from tiny changes
```

**Anomaly Handling:**
```python
if is_anomaly:
    # Cap bandwidth to 1 Mbps (from config ANOMALY_BANDWIDTH_CAP)
    predicted_bw = min(predicted_bw, 1000)
    # Assign lowest priority (3)
```

---

### 5️⃣ **app.py** - Flask Web Server & File Handler

**Purpose:** HTTP interface and background PCAP processing

**Initialization:**
```python
app = Flask(__name__)
CORS(app)  # Enable cross-origin requests

pipeline = PipelineController(
    models_dir=config.MODELS_DIR,
    interface=config.AP_INTERFACE,
    update_interval=10
)
```

---

#### **Background Worker: `pcap_processing_worker()`**

Runs in a daemon thread, monitors uploads/ folder continuously

**Execution Logic:**

```
Loop every 5 seconds (PROCESSING_INTERVAL):
│
├─ Find all .pcap* files in uploads/
│
├─ Filter out already-processed files
│  (Skip if in processed_files dict)
│
├─ Check file stability
│  └─ Wait 2 seconds after last write before processing
│     (Prevents reading incomplete uploads)
│
├─ Sort files by size (smallest first)
│
├─ Process up to 5 files per cycle (MAX_FILES_PER_BATCH)
│  │
│  ├─ FOR EACH FILE:
│  │  │
│  │  ├─ Call: pipeline.process_pcap(pcap_path)
│  │  │
│  │  ├─ IF SUCCESS:
│  │  │  ├─ Move file to processed/ folder
│  │  │  └─ Log: "✓ Processed and moved: filename"
│  │  │
│  │  ├─ IF FAILURE:
│  │  │  ├─ Move file to errors/ folder
│  │  │  └─ Log error message
│  │  │
│  │  └─ Mark file as processed (prevent retry)
│  │
│  └─ Sleep(PROCESSING_INTERVAL = 5 seconds)
│
└─ Repeat
```

**File States:**

```
uploads/
├── new_capture.pcap         (NEW - waiting 2s for stable)
└── stable_capture.pcap      (READY - will be processed)
        ↓ [AFTER PROCESSING]
processed/
├── stable_capture.pcap      (SUCCESS)
└── stable_capture_1.pcap    (name collision handling)

errors/
├── error_corrupt.pcap       (FAILED)
└── error_bad_format_1.pcap  (name collision handling)
```

---

#### **HTTP Endpoints:**

**1. `POST /traffic` - Upload PCAP File**

**Input Options:**

Option A: Multipart form data
```
Content-Type: multipart/form-data
Body: capture=<binary PCAP file>
```

Option B: Raw binary data
```
Content-Type: application/octet-stream
X-Filename: capture.pcap
Body: <binary PCAP file>
```

**Processing:**
```python
1. Check file size (max 50 MB)
2. Generate timestamp-based filename
3. Save to uploads/ folder
4. Return immediately (background worker processes it)
```

**Success Response:**
```json
{
  "status": "success",
  "filename": "20251211_103045_123456_capture.pcap",
  "size_bytes": 1024000,
  "timestamp": "2025-12-11T10:30:45.123456+00:00"
}
```

**Error Response:**
```json
{
  "error": "File too large"
}
```

---

**2. `GET /stats` - Get System Statistics**

**Response:**
```json
{
  "total_bandwidth_mbps": 100,
  "ap_interface": "ap1-wlan1",
  "active_devices": 3,
  "uploads_pending": 2,
  "processed_total": 15,
  "errors_total": 1,
  "uptime": 3600.5,
  "worker_alive": true
}
```

**Where values come from:**
- `active_devices` → From `decision_engine.tc_controller.active_allocations`
- `uploads_pending` → Count of files in uploads/ folder
- `processed_total` → Count of files in processed/ folder
- `errors_total` → Count of files in errors/ folder
- `uptime` → `time.time() - start_time`
- `worker_alive` → `worker_thread.is_alive()`

---

**3. `GET /health` - Health Check**

**Response:**
```json
{
  "status": "healthy",
  "worker_thread": true
}
```

Or if worker crashed:
```json
{
  "status": "worker_dead",
  "worker_thread": false
}
```

---

**4. `GET /` - Home**

**Response:**
```json
{
  "status": "running",
  "service": "ML-Powered WiFi Controller v1.0"
}
```

---

## 🔄 Complete Request Flow Example

### Scenario: User uploads a PCAP with 3 devices, 1 is anomalous

**Step 1: Upload**
```
Client uploads 1.5 MB PCAP file
↓
POST /traffic with file
↓
app.py saves to: uploads/20251211_103045_capture.pcap
↓
Returns immediately (file queued for processing)
```

**Step 2: Background Processing Detects File**
```
pcap_processing_worker() loop (every 5 seconds):
├─ Finds: uploads/20251211_103045_capture.pcap
├─ Waits 2 seconds for file stability
├─ Checks: file not modified, size = 1.5 MB ✓
├─ Calls: pipeline.process_pcap()
```

**Step 3: Feature Extraction**
```
feature_extractor.process_pcap_file():
├─ Reads PCAP, finds 150 packets
├─ Groups by source MAC → 3 flows detected
├─ Extracts 21 features per MAC:
│  ├─ 00:11:22:33:44:55 (5000 bytes/sec)
│  ├─ 00:11:22:33:44:66 (500 bytes/sec)
│  └─ 00:11:22:33:44:77 (100000 bytes/sec - anomalous)
└─ Returns: {'all': DF, 'bandwidth': DF, 'anomaly': DF}
```

**Step 4: ML Predictions**
```
MLModelManager predictions:
├─ predict_bandwidth():
│  ├─ 00:11:22:33:44:55 → 5000 kbps
│  ├─ 00:11:22:33:44:66 → 1000 kbps
│  └─ 00:11:22:33:44:77 → 15000 kbps (would need capping)
│
├─ detect_anomalies():
│  ├─ 00:11:22:33:44:55 → is_anomaly=False, score=0.10
│  ├─ 00:11:22:33:44:66 → is_anomaly=False, score=0.15
│  └─ 00:11:22:33:44:77 → is_anomaly=True, score=0.88 ⚠️
│
└─ classify_traffic():
   ├─ 00:11:22:33:44:55 → video_conference
   ├─ 00:11:22:33:44:66 → web
   └─ 00:11:22:33:44:77 → bulk
```

**Step 5: Anomaly Handling**
```
For 00:11:22:33:44:77 (detected anomaly):
├─ Cap bandwidth: 15000 → min(15000, 1000) = 1000 kbps
├─ Set priority: 3 (lowest)
└─ Note: Log warning "Anomaly detected for 00:11:22:33:44:77"
```

**Step 6: Bandwidth Enforcement**
```
BandwidthDecisionEngine.process_ml_predictions():
├─ Device 1: Check if update needed
│  ├─ Old: None (new device)
│  ├─ New: 5000 kbps, priority 1
│  └─ Action: APPLY ✓
│     └─ Linux TC command executed
│
├─ Device 2: Check if update needed
│  ├─ Old: None (new device)
│  ├─ New: 1000 kbps, priority 2
│  └─ Action: APPLY ✓
│
└─ Device 3: Check if update needed
   ├─ Old: None (new device)
   ├─ New: 1000 kbps, priority 3
   └─ Action: APPLY ✓
      └─ Linux TC command executed with anomaly flag
```

**Step 7: TC Commands Executed (Linux kernel)**
```bash
# For device 00:11:22:33:44:55 (priority 1)
tc class add dev ap1-wlan1 parent 1:10 classid 1:10123 \
  htb rate 5000kbit ceil 10000kbit
tc filter add dev ap1-wlan1 protocol ip parent 1: \
  prio 1 u32 match ether src 00:11:22:33:44:55 flowid 1:10123

# For device 00:11:22:33:44:66 (priority 2)
tc class add dev ap1-wlan1 parent 1:20 classid 1:20456 \
  htb rate 1000kbit ceil 2000kbit
tc filter add dev ap1-wlan1 protocol ip parent 1: \
  prio 2 u32 match ether src 00:11:22:33:44:66 flowid 1:20456

# For device 00:11:22:33:44:77 (priority 3 - anomalous)
tc class add dev ap1-wlan1 parent 1:30 classid 1:30789 \
  htb rate 1000kbit ceil 2000kbit
tc filter add dev ap1-wlan1 protocol ip parent 1: \
  prio 3 u32 match ether src 00:11:22:33:44:77 flowid 1:30789
```

**Step 8: Return Pipeline Response**
```json
{
  "status": "success",
  "timestamp": "2025-12-11T10:30:47.654321",
  "devices_processed": 3,
  "anomalies_detected": 1,
  "predictions": [
    {
      "mac_address": "00:11:22:33:44:55",
      "predicted_bandwidth_kbps": 5000,
      "is_anomaly": false,
      "anomaly_score": 0.10,
      "traffic_class": "video_conference"
    },
    {
      "mac_address": "00:11:22:33:44:66",
      "predicted_bandwidth_kbps": 1000,
      "is_anomaly": false,
      "anomaly_score": 0.15,
      "traffic_class": "web"
    },
    {
      "mac_address": "00:11:22:33:44:77",
      "predicted_bandwidth_kbps": 1000,
      "is_anomaly": true,
      "anomaly_score": 0.88,
      "traffic_class": "bulk"
    }
  ],
  "enforcement": {
    "status": "enforced",
    "devices_updated": 3,
    "active_allocations": 3
  }
}
```

**Step 9: File Management**
```
uploads/20251211_103045_capture.pcap
↓ [Successfully processed]
processed/20251211_103045_capture.pcap
```

**Step 10: Network Effect**
```
Real-time on AP:
├─ Device 00:11:22:33:44:55: Limited to 5 Mbps (HD video conference)
├─ Device 00:11:22:33:44:66: Limited to 1 Mbps (Web browsing)
└─ Device 00:11:22:33:44:77: Limited to 1 Mbps (Rate-limited anomaly)

If device 77 tries to download:
100 Mbps total
├─ 1 Mbps → Device 77 (anomalous - capped)
├─ 4 Mbps → Device 55 (high priority - video)
└─ 1 Mbps → Device 66 (medium priority - web)
```

---

## 🚨 Error Handling & Failure Cases

### **Case 1: Corrupted PCAP File**

```
feature_extractor.extract_from_pcap() fails
↓
Returns: empty DataFrame
↓
PipelineController.process_pcap() catches error
↓
Returns:
{
  "status": "error",
  "message": "Failed to read PCAP: corrupted file"
}
↓
pcap_processing_worker moves file to errors/ folder
↓
File: errors/error_capture.pcap
```

---

### **Case 2: ML Model Not Found**

```
MLModelManager._load_models():
├─ bandwidth_predictor.pkl NOT found
├─ Logs warning: "Bandwidth model not found"
├─ Sets: self.bandwidth_model = None
└─ Continues (graceful degradation)

predict_bandwidth() called:
├─ Checks: if self.bandwidth_model is None
├─ Returns: empty DataFrame
└─ Logs error: "Bandwidth model not loaded"

PipelineController._merge_predictions():
├─ Bandwidth DF is empty
├─ Fills with default: 1000 kbps for all devices
└─ Continues with predictions
```

---

### **Case 3: TC Command Fails (Permission Denied)**

```
TrafficController.apply_allocation() executes:
├─ subprocess.run() returns non-zero exit code
├─ Raises subprocess.CalledProcessError
├─ Caught in try-except
├─ Logs: "Failed to apply allocation for XX:XX:XX:XX:XX:XX"
└─ Does NOT stop pipeline (single device failure isolated)

Result:
├─ Device is NOT rate-limited
├─ Other devices still configured
├─ Admin notified via logs
```

**Fix:** Run app.py with `sudo` or add to sudoers:
```bash
# /etc/sudoers.d/tc-access
your_user ALL=(ALL) NOPASSWD: /sbin/tc
```

---

### **Case 4: Interface Not Found**

```
Config.validate():
├─ Executes: ip link show ap1-wlan1
├─ Returns: error (interface doesn't exist)
├─ Logs warning: "Network interface ap1-wlan1 not found"
└─ Continues (may crash later)

At runtime, first TC command:
├─ subprocess.run() fails
├─ Logs: "Failed to initialize TC"
└─ App continues (TCP pipeline works, enforcement fails)
```

**Fix:** Check interface name:
```bash
ip link show
iwconfig  # For WiFi interfaces
```

---

## 📊 Data Flow Summary Table

| Stage | Input | Process | Output | File |
|-------|-------|---------|--------|------|
| **Upload** | Binary PCAP | Save with timestamp | Queued file | app.py |
| **Detection** | File system | Monitor folder | Stable file | app.py |
| **Feature Extraction** | PCAP packets | Parse & aggregate | 21 features/MAC | feature_extractor.py |
| **ML Inference** | Features | Run 3 models | Predictions | ml_integration.py |
| **Traffic Classification** | Features | Heuristic rules | Traffic class | ml_integration.py |
| **Merge** | 3 predictions | Join on MAC | Complete dataset | ml_integration.py |
| **Priority Assignment** | Traffic + Anomaly | Rule-based logic | Priority 1-3 | bandwidth_enforcer.py |
| **TC Enforcement** | BandwidthAllocation | Linux TC commands | Network QoS | bandwidth_enforcer.py |
| **History** | Predictions | Store recent | History list | ml_integration.py |
| **Response** | All above | JSON serialize | HTTP response | app.py |

---

## 🔐 Security & Config

**Key Config Values (from config.py):**

```python
MAX_FILE_SIZE = 50 MB          # Prevent upload bombs
ALLOWED_EXTENSIONS = {.pcap}   # Whitelist file types
PROCESSING_INTERVAL = 5s       # Check frequency
FILE_STABLE_TIME = 2s          # Wait before processing
ANOMALY_BANDWIDTH_CAP = 1000k  # Hard cap on anomalies
CHANGE_THRESHOLD = 0.15        # 15% before updating TC
TOTAL_BANDWIDTH_MBPS = 100     # Total available
```

---

## 🎯 Summary

```
┌─────────────────────────────────────────────────────────┐
│ COMPLETE BACKEND DATA FLOW                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 1. USER UPLOADS PCAP VIA /traffic                       │
│    └─> app.py saves to uploads/                         │
│                                                         │
│ 2. BACKGROUND WORKER DETECTS FILE                       │
│    └─> pcap_processing_worker() in app.py               │
│                                                         │
│ 3. PIPELINE PROCESSES FILE                              │
│    ├─> feature_extractor: Extract 21 features          │
│    ├─> MLModelManager: Run 3 ML models                  │
│    ├─> Merge predictions                                │
│    └─> PipelineController orchestrates all             │
│                                                         │
│ 4. ENFORCE BANDWIDTH                                    │
│    ├─> BandwidthDecisionEngine assigns priorities      │
│    ├─> TrafficController generates TC commands          │
│    └─> Linux kernel enforces QoS                        │
│                                                         │
│ 5. RETURN RESULTS                                       │
│    └─> JSON response with predictions & status         │
│                                                         │
│ 6. MANAGE FILES                                         │
│    ├─> SUCCESS: Move to processed/                      │
│    └─> FAILURE: Move to errors/                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Takeaways

1. **config.py** = Central config, used by all modules
2. **feature_extractor.py** = PCAP → ML features (16-21 attributes per MAC)
3. **ml_integration.py** = Main orchestrator:
   - Loads ML models
   - Runs predictions (bandwidth, anomaly, classification)
   - Merges predictions
   - Calls bandwidth enforcer
4. **bandwidth_enforcer.py** = ML predictions → Linux TC network rules
5. **app.py** = HTTP server + background file monitor
6. **Config + Security** = File size limits, allowed extensions, permissions

All modules work in **sequence**: Upload → Extract → Predict → Enforce → Report ✓

