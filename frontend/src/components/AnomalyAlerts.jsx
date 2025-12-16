import React, { useState, useEffect } from 'react';
import { AlertTriangle, Clock, Activity, Shield } from 'lucide-react';
import apiService from '../services/api';

const AnomalyAlerts = () => {
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAnomalies = async () => {
    try {
      const data = await apiService.getAnomalies();
      setAnomalies(data.anomalies || []);
    } catch (err) {
      console.error('Failed to fetch anomalies:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnomalies();
    const interval = setInterval(fetchAnomalies, 5000);
    return () => clearInterval(interval);
  }, []);

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    
    return date.toLocaleDateString();
  };

  const getAnomalyScoreColor = (score) => {
    if (score >= 0.8) return 'from-red-500 to-pink-500';
    if (score >= 0.6) return 'from-orange-500 to-amber-500';
    return 'from-yellow-500 to-amber-500';
  };

  if (loading) {
    return (
      <div className="glass-card p-6">
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="loading-shimmer h-20 rounded-2xl"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-gray-200/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-red-500 to-pink-500">
              <AlertTriangle className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Anomaly Alerts</h2>
              <p className="text-sm text-gray-600">{anomalies.length} active alerts</p>
            </div>
          </div>
        </div>
      </div>

      {/* Anomaly List */}
      <div className="max-h-[600px] overflow-y-auto">
        {anomalies.length === 0 ? (
          <div className="p-16 text-center">
            <div className="inline-flex p-4 rounded-full bg-gradient-to-br from-green-500 to-emerald-500 mb-4">
              <Shield className="w-12 h-12 text-white" />
            </div>
            <p className="text-gray-900 font-semibold mb-2">All Clear!</p>
            <p className="text-sm text-gray-600">No anomalies detected</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200/50">
            {anomalies.map((anomaly, index) => (
              <div
                key={`${anomaly.mac_address}-${index}`}
                className="p-4 transition-smooth hover:bg-white/50"
              >
                <div className="flex items-start gap-3">
                  {/* Score Indicator */}
                  <div className={`p-2 rounded-xl bg-gradient-to-br ${getAnomalyScoreColor(anomaly.anomaly_score)}`}>
                    <AlertTriangle className="w-4 h-4 text-white" />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-semibold text-gray-900 text-sm truncate">
                        {anomaly.mac_address}
                      </span>
                      <span className="badge-pill badge-error !text-xs">
                        {(anomaly.anomaly_score * 100).toFixed(0)}% risk
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <p className="text-gray-500 mb-0.5">Traffic Type</p>
                        <p className="font-medium text-gray-900 capitalize">
                          {anomaly.traffic_class?.replace('_', ' ')}
                        </p>
                      </div>
                      
                      <div>
                        <p className="text-gray-500 mb-0.5">Bandwidth</p>
                        <p className="font-medium text-gray-900">
                          {anomaly.bandwidth_kbps >= 1000 
                            ? `${(anomaly.bandwidth_kbps / 1000).toFixed(1)} Mbps`
                            : `${anomaly.bandwidth_kbps} kbps`}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 mt-2 text-gray-500">
                      <Clock className="w-3 h-3" />
                      <span className="text-xs">
                        {formatTimestamp(anomaly.timestamp)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AnomalyAlerts;