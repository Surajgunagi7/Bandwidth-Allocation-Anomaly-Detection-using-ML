bandwidth-allocation-project/
├── backend/
│   ├── app.py                      # Main Flask application
│   ├── feature_extractor.py        # PCAP → Features (from artifact)
│   ├── bandwidth_enforcer.py       # TC enforcement logic (from artifact)
│   ├── ml_integration.py           # ML pipeline controller (from artifact)
│   ├── models/
│   │   ├── bandwidth_predictor.pkl # Trained Random Forest
│   │   ├── anomaly_detector.pkl    # Trained Isolation Forest
│   │   └── feature_scaler.pkl      # Feature normalization
│   ├── uploads/                    # Temporary PCAP storage
│   └── requirements.txt
│
├── training/
│   ├── dataset_generator.py        # Scenario simulation (from artifact)
│   ├── train_bandwidth_model.py    # Train Random Forest
│   ├── train_anomaly_model.py      # Train Isolation Forest
│   └── training_data/
│       ├── pcap_captures/          # Raw PCAPs from simulations
│       ├── training_dataset.csv    # Extracted features + labels
│       └── dataset_metadata.csv    # Scenario metadata
│
├── mininet/
│   ├── topology.py                 # Mininet-WiFi network setup
│   ├── traffic_generator.py        # Generate different traffic patterns
│   └── capture_daemon.py           # Periodic PCAP upload to backend
│
├── dashboard/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── BandwidthChart.jsx
│   │   │   ├── AnomalyAlerts.jsx
│   │   │   └── DeviceTable.jsx
│   │   └── App.jsx
│   └── package.json
│
└── docs/
    ├── setup_guide.md
    └── api_documentation.md