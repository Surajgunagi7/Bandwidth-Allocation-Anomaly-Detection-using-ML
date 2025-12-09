#!/usr/bin/env python3
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib
from feature_extractor import process_pcap_file
from pathlib import Path

DATA_DIR = Path("../pcap_captures")
MODEL_DIR = Path("../models")
MODEL_DIR.mkdir(exist_ok=True)

features = []
labels = []

for pcap_file in DATA_DIR.glob("*.pcap*"):
    scenario_name = pcap_file.name.split("_")[0]
    label = 2000  # default
    if "video" in scenario_name:
        label = 10000
    elif "normal" in scenario_name:
        label = 3000
    elif "ddos" in scenario_name:
        label = 500
    
    result = process_pcap_file(str(pcap_file))
    if not result['bandwidth'].empty:
        df = result['bandwidth']
        features.extend(df.drop(columns=['mac_address']).values)
        labels.extend([label] * len(df))

X = pd.DataFrame(features)
y = labels

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

model = RandomForestRegressor(n_estimators=200, random_state=42)
model.fit(X_scaled, y)

joblib.dump(model, MODEL_DIR / "bandwidth_predictor.pkl")
joblib.dump(scaler, MODEL_DIR / "feature_scaler.pkl")
print("Bandwidth model trained & saved!")