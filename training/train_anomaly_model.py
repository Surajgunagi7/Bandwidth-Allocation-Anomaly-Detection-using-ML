#!/usr/bin/env python3
from sklearn.ensemble import IsolationForest
import joblib
from feature_extractor import process_pcap_file
from pathlib import Path

DATA_DIR = Path("../pcap_captures")
MODEL_DIR = Path("../models")

X_normal = []
for pcap_file in DATA_DIR.glob("*normal*.pcap*"):
    result = process_pcap_file(str(pcap_file))
    if not result['anomaly'].empty:
        X_normal.extend(result['anomaly'].drop(columns=['mac_address']).values)

model = IsolationForest(contamination=0.1, random_state=42)
model.fit(X_normal)

joblib.dump(model, MODEL_DIR / "anomaly_detector.pkl")
print("Anomaly model trained!")