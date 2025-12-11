#!/usr/bin/env python3
"""
System Diagnostic Script
Run this to identify configuration issues before starting the backend
"""

import subprocess
import os
import sys
from pathlib import Path
import json

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def print_check(name, passed, details=""):
    status = "✅" if passed else "❌"
    print(f"{status} {name}")
    if details:
        print(f"   → {details}")

def check_python_version():
    print_header("Python Environment")
    version = sys.version_info
    passed = version.major == 3 and version.minor >= 8
    print_check(
        "Python Version",
        passed,
        f"{version.major}.{version.minor}.{version.micro} ({'OK' if passed else 'Need 3.8+'})"
    )
    return passed

def check_packages():
    print_header("Required Packages")
    required = {
        'scapy': 'scapy',
        'numpy': 'numpy',
        'pandas': 'pandas',
        'scipy': 'scipy',
        'sklearn': 'scikit-learn',
        'flask': 'flask',
        'flask_cors': 'flask-cors',
        'joblib': 'joblib'
    }
    
    all_ok = True
    for module, package in required.items():
        try:
            __import__(module)
            print_check(f"{package}", True, "Installed")
        except ImportError:
            print_check(f"{package}", False, f"Missing - Install: pip install {package}")
            all_ok = False
    
    return all_ok

def check_directories():
    print_header("Directory Structure")
    required_dirs = ['uploads', 'processed', 'models', 'logs']
    base_dir = Path(__file__).parent
    
    all_ok = True
    for dir_name in required_dirs:
        dir_path = base_dir / dir_name
        exists = dir_path.exists()
        print_check(
            f"{dir_name}/",
            exists,
            str(dir_path) if exists else f"Missing - Create: mkdir {dir_name}"
        )
        if not exists:
            all_ok = False
    
    return all_ok

def check_ml_models():
    print_header("ML Models")
    models_dir = Path(__file__).parent / 'models'
    required_models = [
        'bandwidth_predictor.pkl',
        'anomaly_detector.pkl',
        'bandwidth_scaler.pkl',
        'anomaly_scaler.pkl'
    ]
    
    all_ok = True
    for model in required_models:
        model_path = models_dir / model
        exists = model_path.exists()
        size = model_path.stat().st_size if exists else 0
        print_check(
            model,
            exists,
            f"{size/1024:.1f} KB" if exists else "Missing"
        )
        if not exists:
            all_ok = False
    
    if not all_ok:
        print("\n⚠️  Models missing - You need to train models first")
        print("   Run: python train_models.py (if available)")
    
    return all_ok

def check_network_interface():
    print_header("Network Configuration")
    
    # Check for common interface names
    interfaces_to_check = ['ap1-wlan1', 'wlan0', 'eth0', 'ap0']
    
    try:
        result = subprocess.run(
            'ip link show',
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            output = result.stdout
            found_interfaces = []
            
            for line in output.split('\n'):
                for iface in interfaces_to_check:
                    if iface in line:
                        found_interfaces.append(iface)
            
            if found_interfaces:
                print_check(
                    "Network Interfaces",
                    True,
                    f"Found: {', '.join(found_interfaces)}"
                )
                print(f"\n   Update config.py with: AP_INTERFACE = '{found_interfaces[0]}'")
                return True
            else:
                print_check(
                    "Network Interfaces",
                    False,
                    "No WiFi AP interfaces found"
                )
                print("\n   Available interfaces:")
                for line in output.split('\n'):
                    if ':' in line and 'link/' in line:
                        print(f"   • {line.split(':')[1].strip()}")
                return False
        else:
            print_check("Network Interfaces", False, "Could not list interfaces")
            return False
            
    except Exception as e:
        print_check("Network Interfaces", False, str(e))
        return False

def check_tc_availability():
    print_header("Traffic Control (TC)")
    
    # Check if tc command exists
    try:
        result = subprocess.run(
            'which tc',
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print_check("TC command", True, result.stdout.strip())
        else:
            print_check("TC command", False, "Not found - Install: apt-get install iproute2")
            return False
    except Exception as e:
        print_check("TC command", False, str(e))
        return False
    
    # Check permissions
    try:
        result = subprocess.run(
            'tc qdisc show',
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print_check("TC permissions", True, "Can run TC commands")
            return True
        else:
            print_check(
                "TC permissions",
                False,
                "Permission denied - Run with: sudo python app.py"
            )
            return False
    except Exception as e:
        print_check("TC permissions", False, str(e))
        return False

def check_config_file():
    print_header("Configuration File")
    
    config_path = Path(__file__).parent / 'config.py'
    
    if not config_path.exists():
        print_check("config.py", False, "File not found")
        return False
    
    print_check("config.py", True, "File exists")
    
    # Try to import and check key values
    try:
        sys.path.insert(0, str(config_path.parent))
        from config import Config
        
        checks = {
            'TOTAL_BANDWIDTH_MBPS': getattr(Config, 'TOTAL_BANDWIDTH_MBPS', None),
            'AP_INTERFACE': getattr(Config, 'AP_INTERFACE', None),
            'UPLOAD_DIR': getattr(Config, 'UPLOAD_DIR', None),
            'MODELS_DIR': getattr(Config, 'MODELS_DIR', None),
        }
        
        all_ok = True
        for key, value in checks.items():
            has_value = value is not None
            print_check(f"  {key}", has_value, str(value) if has_value else "Not set")
            if not has_value:
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print_check("Config Import", False, str(e))
        return False

def generate_fixes():
    print_header("Quick Fixes")
    
    print("""
# 1. Create missing directories
mkdir -p uploads processed models logs errors

# 2. Install missing packages
pip install scapy numpy pandas scipy scikit-learn flask flask-cors joblib

# 3. Fix permissions (if needed)
sudo python app.py

# 4. Verify network interface
ip link show

# 5. Test TC commands
sudo tc qdisc show

# 6. Check for warnings in logs
tail -f logs/*.log
    """)

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║  ML-Powered WiFi Backend - System Diagnostic             ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    results = {
        'Python': check_python_version(),
        'Packages': check_packages(),
        'Directories': check_directories(),
        'ML Models': check_ml_models(),
        'Network': check_network_interface(),
        'TC': check_tc_availability(),
        'Config': check_config_file(),
    }
    
    print_header("Summary")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nChecks Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All checks passed! Ready to start backend.")
        print("\nRun: sudo python app.py")
    else:
        print(f"\n❌ {total - passed} issues found. See fixes below:")
        generate_fixes()
        
        print("\n⚠️  Critical issues:")
        for check, status in results.items():
            if not status:
                print(f"  • {check}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)