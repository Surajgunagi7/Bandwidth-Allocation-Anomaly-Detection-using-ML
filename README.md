# Bandwidth Allocation Anomaly Detection using ML

## Overview
This project implements a machine learning-based system for detecting anomalies in bandwidth allocation. It consists of a backend service, a frontend dashboard, and a Mininet-based network simulation environment.

## Project Structure
- **backend/**: Contains the Flask backend for handling API requests and processing data.
- **frontend/**: Contains the React application for the user interface.
- **mininet/**: Contains scripts for simulating network topologies.
- **training/**: Contains Jupyter notebooks for training machine learning models.

## Setup Instructions
### Backend
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Set up a virtual environment and activate it:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the backend application:
   ```bash
   sudo venv/bin/python app.py
   ```

### Mininet
1. Run the topology script with sudo:
   ```bash
   sudo python3 topology.py
   ```

### Frontend
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install the required packages:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```

## Features
- **Dynamic Bandwidth Detection**: The system can dynamically detect and allocate bandwidth based on network conditions.
- **Anomaly Detection**: Utilizes machine learning models to identify anomalies in bandwidth usage.
- **User Dashboard**: A web interface for monitoring and controlling bandwidth allocation.

## Conclusion
This project aims to provide an intelligent solution for managing network bandwidth using machine learning techniques. For more details, refer to the individual module documentation within the project.bash



## Configuration

### Option 1: Environment Variables (.env file)
```bash
# Network
AP_INTERFACE=ap1-wlan1
TOTAL_BANDWIDTH_MBPS=100  # Optional - will auto-detect if not set

# Anomaly Detection
NO_ANOMALY_MODE=true  # Set to false to enable anomaly detection

# Processing
PROCESSING_INTERVAL=9
TC_UPDATE_INTERVAL=9

# ML
ML_BATCH_SIZE=3
PREDICTION_THRESHOLD=0.65
```

### Option 2: Dynamic Configuration via API

**Detect and set bandwidth:**
```bash
# Detect bandwidth
python3 detect_bandwidth.py ap1-wlan1

# Detect and set via API
python3 detect_bandwidth.py ap1-wlan1 --set-api
```

**Manually set bandwidth via API:**
```bash
curl -X POST http://localhost:5000/api/bandwidth/config \
  -H "Content-Type: application/json" \
  -d '{"bandwidth_mbps": 100}'
```

## API Endpoints

### Core Endpoints
- `POST /traffic` - Upload PCAP files
- `GET /stats` - System statistics
- `GET /health` - Health check

### Configuration Endpoints
- `GET /api/bandwidth/config` - Get current bandwidth config
- `POST /api/bandwidth/config` - Set bandwidth dynamically
- `GET /api/devices` - Get active device allocations
- `GET /api/anomalies` - Get recent anomaly alerts
- `GET /api/history` - Get prediction history

### Policy Control Endpoints
- `POST /api/policy/mode` - Set global mode (auto/equal/manual)
- `POST /api/policy/override` - Set device-specific override
- `DELETE /api/policy/override/<mac>` - Clear device override
- `POST /api/reset` - Reset all TC rules

## Troubleshooting

### Issue 1: "RTNETLINK answers: File exists"

**Symptoms**: TC class creation fails with "File exists" error

**Solution**:
```bash
# Manual cleanup
sudo tc qdisc del dev ap1-wlan1 root

# Restart application
sudo python3 app.py
```

The application now does this automatically on startup.

### Issue 2: Low Bandwidth Allocations

**Symptoms**: Devices getting 314 kbps instead of fair share of 100 Mbps

**Check**:
```bash
# View current allocations
curl http://localhost:5000/api/devices

# Check total bandwidth config
curl http://localhost:5000/api/bandwidth/config
```

**Solution**:
```bash
# Set correct bandwidth
curl -X POST http://localhost:5000/api/bandwidth/config \
  -H "Content-Type: application/json" \
  -d '{"bandwidth_mbps": 100}'
```

### Issue 3: AP MAC Not Detected

**Symptoms**: AP traffic being managed (shouldn't be)

**Check**:
```bash
# Verify AP MAC
ip link show ap1-wlan1 | grep "link/ether"
```

**Fix**: The system auto-detects AP MAC. If it fails, check logs:
```bash
tail -f logs/app.log | grep "Detected AP MAC"
```

### Issue 4: No Traffic Being Processed

**Symptoms**: PCAP files uploaded but no bandwidth allocation

**Check**:
```bash
# Check worker status
curl http://localhost:5000/health

# Check logs
tail -f logs/app.log

# Check pending files
ls -lh uploads/
```

**Solution**:
```bash
# Restart application (supervisor will restart worker)
sudo python3 app.py
```

### Issue 5: Permission Denied Errors

**Symptoms**: "Operation not permitted" when applying TC rules

**Solution**:
```bash
# Run with sudo
sudo python3 app.py

# Verify TC permissions
sudo tc qdisc show
```

## Logging

All logs are now written to files in the `logs/` directory:

```bash
# View all logs
tail -f logs/app.log

# Filter for errors only
tail -f logs/app.log | grep ERROR

# Filter for bandwidth allocations
tail -f logs/app.log | grep "Applied.*kbps"

# View TC operations
tail -f logs/app.log | grep "bandwidth_enforcer"
```

Console output is limited to:
- ⚠️ Warnings
- ❌ Errors
- ✅ Success confirmations (minimal)

## Testing

### Test 1: Bandwidth Detection
```bash
sudo python3 detect_bandwidth.py ap1-wlan1
```

Expected output:
```json
{
  "interface": "ap1-wlan1",
  "bandwidth_mbps": 100,
  "method": "ethtool",
  "raw_output": "Speed: 100Mb/s"
}
```

### Test 2: PCAP Processing
```bash
# Upload test PCAP
curl -X POST -F "capture=@test.pcap" http://localhost:5000/traffic

# Check stats
curl http://localhost:5000/stats

# Check devices
curl http://localhost:5000/api/devices
```

### Test 3: TC Rules
```bash
# View current TC configuration
sudo tc -s qdisc show dev ap1-wlan1
sudo tc -s class show dev ap1-wlan1
sudo tc -s filter show dev ap1-wlan1
```

### Test 4: Manual Override
```bash
# Set device to 5 Mbps, priority 1 (high)
curl -X POST http://localhost:5000/api/policy/override \
  -H "Content-Type: application/json" \
  -d '{
    "mac_address": "00:11:22:33:44:55",
    "bandwidth_kbps": 5000,
    "priority": 1
  }'

# Verify
curl http://localhost:5000/api/devices
```

## Performance Tips

1. **Adjust Processing Interval**: Set `PROCESSING_INTERVAL` in .env to balance responsiveness vs CPU usage

2. **Batch Size**: Increase `ML_BATCH_SIZE` if processing many PCAPs simultaneously

3. **Anomaly Detection**: Disable with `NO_ANOMALY_MODE=true` if not needed (saves CPU)

4. **Log Rotation**: Implement log rotation for production:
   ```bash
   # Add to crontab
   0 0 * * * find /path/to/logs -name "*.log" -mtime +7 -delete
   ```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Flask Backend (app.py)                │
├─────────────────────────────────────────────────────────┤
│  - PCAP Upload & Processing Worker                      │
│  - API Endpoints (REST)                                  │
│  - Worker Supervisor (auto-restart)                      │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│          ML Pipeline (ml_integration.py)                 │
├─────────────────────────────────────────────────────────┤
│  - Feature Extraction (feature_extractor.py)             │
│  - ML Models (bandwidth, anomaly, traffic class)         │
│  - Temporal Smoothing                                    │
│  - Policy Layer (overrides, modes)                       │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│     Bandwidth Enforcer (bandwidth_enforcer.py)           │
├─────────────────────────────────────────────────────────┤
│  - Traffic Control (TC) via HTB                          │
│  - Class & Filter Management                             │
│  - Priority-based QoS                                    │
│  - Normalization & Distribution                          │
└─────────────────────────────────────────────────────────┘
```

## Key Features

✅ **Dynamic Bandwidth Detection**: Auto-detects interface capacity  
✅ **Robust TC Management**: Proper cleanup and collision prevention  
✅ **Minimum Guarantees**: Every device gets at least 512 kbps  
✅ **Smart Logging**: File-based logs with minimal console output  
✅ **API Control**: Full REST API for monitoring and configuration  
✅ **Policy Overrides**: Manual control when needed  
✅ **Temporal Smoothing**: Prevents allocation jitter  
✅ **Anomaly Detection**: Optional malicious traffic detection  
✅ **Auto-recovery**: Worker supervisor ensures uptime  

## Production Deployment

1. **Use systemd service**:
```ini
[Unit]
Description=ML WiFi Controller
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

2. **Configure log rotation**
3. **Set up monitoring** (health endpoint)
4. **Enable firewall rules** for Flask port
5. **Use production WSGI server** (gunicorn)

## Support

For issues:
1. Check `logs/app.log`
2. Run `/health` endpoint
3. Verify TC permissions with `sudo tc qdisc show`
4. Check interface exists: `ip link show ap1-wlan1`