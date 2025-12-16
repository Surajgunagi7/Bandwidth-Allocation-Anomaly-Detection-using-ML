import React, { useState, useEffect } from 'react';
import { AlertTriangle, X, Clock, Activity } from 'lucide-react';
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
    if (score >= 0.8) return 'text-red-600';
    if (score >= 0.6) return 'text-orange-600';
    return 'text-yellow-600';
  };

  const getAnomalyScoreBg = (score) => {
    if (score >= 0.8) return 'bg-red-50 border-red-200';
    if (score >= 0.6) return 'bg-orange-50 border-orange-200';
    return 'bg-yellow-50 border-yellow-200';
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-16 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <AlertTriangle className="w-5 h-5 text-red-600 mr-2" />
            <h2 className="text-xl font-semibold text-gray-900">Anomaly Alerts</h2>
          </div>
          <span className="px-3 py-1 bg-red-100 text-red-800 text-xs font-medium rounded-full">
            {anomalies.length} active
          </span>
        </div>
      </div>

      <div className="max-h-96 overflow-y-auto">
        {anomalies.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Activity className="w-8 h-8 text-green-600" />
            </div>
            <p className="text-gray-600 font-medium">All Clear!</p>
            <p className="text-sm text-gray-500 mt-2">No anomalies detected</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {anomalies.map((anomaly, index) => (
              <div
                key={`${anomaly.mac_address}-${index}`}
                className={`p-4 border-l-4 ${getAnomalyScoreBg(anomaly.anomaly_score)}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center mb-2">
                      <AlertTriangle className={`w-4 h-4 mr-2 ${getAnomalyScoreColor(anomaly.anomaly_score)}`} />
                      <span className="font-medium text-gray-900">
                        {anomaly.mac_address}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <p className="text-gray-500">Traffic Type</p>
                        <p className="font-medium text-gray-900 capitalize">
                          {anomaly.traffic_class?.replace('_', ' ')}
                        </p>
                      </div>
                      
                      <div>
                        <p className="text-gray-500">Bandwidth</p>
                        <p className="font-medium text-gray-900">
                          {anomaly.bandwidth_kbps >= 1000 
                            ? `${(anomaly.bandwidth_kbps / 1000).toFixed(1)} Mbps`
                            : `${anomaly.bandwidth_kbps} kbps`}
                        </p>
                      </div>
                      
                      <div>
                        <p className="text-gray-500">Anomaly Score</p>
                        <p className={`font-medium ${getAnomalyScoreColor(anomaly.anomaly_score)}`}>
                          {(anomaly.anomaly_score * 100).toFixed(0)}%
                        </p>
                      </div>
                      
                      <div className="flex items-center text-gray-500">
                        <Clock className="w-3 h-3 mr-1" />
                        <span className="text-xs">
                          {formatTimestamp(anomaly.timestamp)}
                        </span>
                      </div>
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