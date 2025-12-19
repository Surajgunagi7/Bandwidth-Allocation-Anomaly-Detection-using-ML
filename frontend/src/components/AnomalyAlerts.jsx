import React, { useState, useEffect } from 'react';
import { AlertTriangle, Clock, Activity, TrendingUp, Shield } from 'lucide-react';
import api from '../services/api';
import { cn } from '@/lib/utils';

const AnomalyAlerts = () => {
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAnomalies = async () => {
    try {
      const data = await api.getAnomalies();
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
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    
    return date.toLocaleDateString();
  };

  const getSeverityConfig = (score) => {
    if (score >= 0.8) return {
      bg: 'bg-gradient-to-br from-red-50 to-rose-50',
      border: 'border-red-200',
      borderLeft: 'border-l-red-500',
      badge: 'bg-gradient-to-r from-red-500 to-rose-600 text-white',
      icon: 'text-red-600',
      glow: 'shadow-red-100',
      label: 'Critical'
    };
    if (score >= 0.6) return {
      bg: 'bg-gradient-to-br from-amber-50 to-orange-50',
      border: 'border-amber-200',
      borderLeft: 'border-l-amber-500',
      badge: 'bg-gradient-to-r from-amber-500 to-orange-600 text-white',
      icon: 'text-amber-600',
      glow: 'shadow-amber-100',
      label: 'Warning'
    };
    return {
      bg: 'bg-gradient-to-br from-yellow-50 to-amber-50',
      border: 'border-yellow-200',
      borderLeft: 'border-l-yellow-500',
      badge: 'bg-gradient-to-r from-yellow-500 to-amber-600 text-white',
      icon: 'text-yellow-600',
      glow: 'shadow-yellow-100',
      label: 'Notice'
    };
  };

  // always render component; loading overlay is shown below when `loading` is true
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden hover:shadow-md transition-shadow h-full flex flex-col relative">
      {loading && (
        <div className="absolute inset-0 bg-white/40 backdrop-blur-sm rounded-lg flex items-center justify-center z-10 pointer-events-none">
          <div className="flex flex-col items-center gap-3">
            <div className="relative w-12 h-12">
              <div className="absolute inset-0 border-4 border-slate-100 rounded-full"></div>
              <div className="absolute inset-0 border-4 border-transparent border-t-red-500 rounded-full animate-spin"></div>
            </div>
            <p className="text-slate-600 font-medium text-sm">Scanning anomalies...</p>
          </div>
        </div>
      )}
      {/* Premium Header */}
      <div className="relative overflow-hidden shrink-0">
        <div className="absolute inset-0 bg-linear-to-r from-red-500 via-rose-500 to-pink-500 opacity-[0.03]"></div>
        <div className="relative p-8 border-b border-slate-200/60 bg-linear-to-r from-slate-50/50 to-red-50/30 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="p-3 rounded-xl bg-linear-to-br from-red-500 to-rose-600 shadow-lg shadow-red-500/20">
                  <AlertTriangle className="w-6 h-6 text-white" />
                </div>
                {anomalies.length > 0 && (
                  <div className="absolute -top-1.5 -right-1.5 w-6 h-6 bg-white rounded-full flex items-center justify-center shadow-sm border border-red-100">
                    <span className="text-xs font-bold text-red-600">{anomalies.length > 9 ? '9+' : anomalies.length}</span>
                  </div>
                )}
              </div>
              <div>
                <h2 className="text-xl font-bold font-display text-slate-900">Security Alerts</h2>
                <p className="text-sm text-slate-500 mt-1 flex items-center gap-2">
                  <Activity className="w-3.5 h-3.5" />
                  {anomalies.length} active alert{anomalies.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
            <Shield className="w-8 h-8 text-slate-200" />
          </div>
        </div>
      </div>

      {/* Alerts List */}
      <div className="divide-y divide-slate-100 overflow-y-auto custom-scrollbar flex-1 min-h-75">
        {anomalies.length === 0 ? (
          <div className="p-12 text-center h-full flex flex-col items-center justify-center">
            <div className="relative inline-block mb-6">
              <div className="absolute inset-0 bg-emerald-500 rounded-full opacity-20 animate-pulse"></div>
              <div className="relative p-6 rounded-full bg-linear-to-br from-emerald-50 to-teal-50 border-2 border-emerald-100/50">
                <Shield className="w-12 h-12 text-emerald-600" />
              </div>
            </div>
            <h3 className="text-lg font-bold font-display text-slate-900 mb-2">All Systems Secure</h3>
            <p className="text-slate-500 font-medium">No anomalies detected</p>
            <p className="text-xs text-slate-400 mt-2">Continuous monitoring active</p>
          </div>
        ) : (
          anomalies.map((anomaly, index) => {
            const config = getSeverityConfig(anomaly.anomaly_score);
            return (
              <div
                key={index}
                className={cn(
                  "p-6 border-l-4 transition-all duration-300 group relative overflow-hidden hover:bg-white",
                  config.borderLeft,
                  config.bg
                )}
              >
                {/* Animated background effect */}
                <div className="absolute inset-0 bg-linear-to-r from-transparent via-white/40 to-transparent opacity-0 group-hover:opacity-100 transform -skew-x-12 -translate-x-full group-hover:translate-x-full transition-all duration-1000"></div>
                
                <div className="relative flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-3">
                      <AlertTriangle className={cn("w-5 h-5 shrink-0", config.icon)} />
                      <div className="flex-1">
                        <p className="text-sm font-bold text-slate-900 mb-0.5">
                          {anomaly.device_name || anomaly.mac_address || 'Unknown Device'}
                        </p>
                        <p className="text-xs text-slate-600 font-medium">
                          {anomaly.traffic_class ? `${anomaly.traffic_class}` : 'Unusual pattern detected'}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-4 text-xs text-slate-500 ml-8">
                      <div className="flex items-center gap-1.5 bg-white/50 px-2 py-1 rounded-md">
                        <Clock className="w-3.5 h-3.5" />
                        <span>{formatTimestamp(anomaly.timestamp)}</span>
                      </div>
                      {anomaly.bandwidth_kbps && (
                        <div className="flex items-center gap-1.5 bg-white/50 px-2 py-1 rounded-md">
                          <TrendingUp className="w-3.5 h-3.5" />
                          <span>{(anomaly.bandwidth_kbps / 1000).toFixed(2)} Mbps</span>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="text-right shrink-0">
                    <div className={cn("px-3 py-1 rounded-full text-[10px] uppercase tracking-wider font-bold shadow-sm mb-2 inline-block", config.badge)}>
                      {config.label}
                    </div>
                    <div className="text-xs font-bold text-slate-500 text-right">
                      {(anomaly.anomaly_score * 100).toFixed(0)}% risk
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default AnomalyAlerts;