#!/bin/bash
# Startup script with pre-flight checks

set -e

echo "=========================================="
echo "ML WiFi Controller - Startup Script"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: Must run with sudo"
    echo "Usage: sudo ./start.sh"
    exit 1
fi

# Check if interface exists
INTERFACE="${AP_INTERFACE:-ap1-wlan1}"
if ! ip link show "$INTERFACE" &>/dev/null; then
    echo "⚠️  Warning: Interface $INTERFACE not found"
    echo "Available interfaces:"
    ip link show | grep -E "^[0-9]+:" | awk '{print $2}' | tr -d ':'
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1-2)
echo "✓ Python version: $PYTHON_VERSION"

# Check if required Python packages are installed
echo "Checking dependencies..."
if ! python3 -c "import flask" 2>/dev/null; then
    echo "⚠️  Flask not found. Install with: pip install -r requirements.txt"
    exit 1
fi

# Check if tc is available
if ! command -v tc &>/dev/null; then
    echo "❌ Error: tc (traffic control) not found"
    echo "Install with: apt-get install iproute2"
    exit 1
fi

# Check if models exist
if [ ! -f "models/bandwidth_predictor.pkl" ]; then
    echo "⚠️  Warning: ML models not found in models/"
    echo "The system will run but predictions may be suboptimal."
fi

# Clean up any existing TC configuration
echo "Cleaning up existing TC configuration..."
tc qdisc del dev "$INTERFACE" root 2>/dev/null || true
tc qdisc del dev "$INTERFACE" ingress 2>/dev/null || true

# Detect bandwidth
echo "Detecting interface bandwidth..."
if [ -f "detect_bandwidth.py" ]; then
    BANDWIDTH_INFO=$(python3 detect_bandwidth.py "$INTERFACE" 2>/dev/null || echo "")
    if [ -n "$BANDWIDTH_INFO" ]; then
        echo "$BANDWIDTH_INFO"
    fi
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p uploads processed logs models

# Start the application
echo ""
echo "=========================================="
echo "Starting ML WiFi Controller..."
echo "=========================================="
echo "Interface: $INTERFACE"
echo "Logs: logs/app.log"
echo "API: http://localhost:5000"
echo "=========================================="
echo ""

# Run the application
python3 app.py