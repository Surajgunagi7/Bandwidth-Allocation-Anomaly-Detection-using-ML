import React, { useEffect, useState } from 'react';
import { AlertTriangle, Clock, TrendingUp, Shield } from 'lucide-react';
import api from '@/services/api';
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

  const formatTimestamp = (ts) => {
    if (!ts) return 'Unknown time';
    const date = ts > 1e12 ? new Date(ts) : new Date(ts * 1000);
    const diff = Math.floor((Date.now() - date.getTime()) / 60000);
    if (diff < 1) return 'Just now';
    if (diff < 60) return `${diff}m ago`;
    if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
    return date.toLocaleDateString();
  };

  const severity = (score = 0) => {
    if (score >= 0.8) return { label: 'Critical', color: 'red' };
    if (score >= 0.6) return { label: 'Warning', color: 'amber' };
    return { label: 'Notice', color: 'yellow' };
  };

  return (
    <div className="bg-white rounded-xl border overflow-hidden relative">
      {loading && (
        <div className="absolute inset-0 bg-white/50 flex items-center justify-center z-10">
          <p className="text-slate-500 font-medium">Scanning anomalies…</p>
        </div>
      )}

      <div className="p-6 border-b bg-slate-50 flex items-center gap-3">
        <AlertTriangle className="w-6 h-6 text-red-600" />
        <div>
          <h2 className="font-bold text-slate-900">Security Alerts</h2>
          <p className="text-sm text-slate-500">
            {anomalies.length} active alert{anomalies.length !== 1 && 's'}
          </p>
        </div>
      </div>

      <div className="divide-y max-h-96 overflow-y-auto">
        {anomalies.length === 0 ? (
          <div className="p-10 text-center text-slate-500">
            <Shield className="w-10 h-10 mx-auto mb-2 text-emerald-500" />
            No anomalies detected
          </div>
        ) : (
          anomalies.map((a, i) => {
            const sev = severity(a.anomaly_score);
            return (
              <div key={i} className="p-5 flex justify-between gap-4">
                <div>
                  <p className="font-semibold">
                    Device {a.mac?.slice(-5)}
                  </p>
                  <p className="text-xs text-slate-500 font-mono">{a.mac}</p>

                  <div className="flex gap-4 mt-2 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTimestamp(a.timestamp)}
                    </span>
                    {a.bandwidth_kbps && (
                      <span className="flex items-center gap-1">
                        <TrendingUp className="w-3 h-3" />
                        {(a.bandwidth_kbps / 1000).toFixed(2)} Mbps
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-right">
                  <span
                    className={cn(
                      'px-3 py-1 rounded-full text-xs font-bold',
                      sev.color === 'red' && 'bg-red-100 text-red-700',
                      sev.color === 'amber' && 'bg-amber-100 text-amber-700',
                      sev.color === 'yellow' && 'bg-yellow-100 text-yellow-700'
                    )}
                  >
                    {sev.label}
                  </span>
                  <p className="text-xs font-semibold text-slate-500 mt-1">
                    {(a.anomaly_score * 100).toFixed(0)}% risk
                  </p>
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
