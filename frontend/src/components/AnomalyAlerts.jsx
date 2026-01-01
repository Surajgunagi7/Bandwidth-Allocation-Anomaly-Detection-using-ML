import React, { useEffect, useState } from 'react';
import { AlertTriangle, TrendingUp, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';

const AnomalyAlerts = ({ anomalies, loading }) => {
  
  const severity = (score = 0) => {
    if (score >= 0.8) return { label: 'Critical', color: 'red' };
    if (score >= 0.6) return { label: 'Warning', color: 'amber' };
    return { label: 'Notice', color: 'yellow' };
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl border p-8 text-center text-slate-500">
        Scanning anomalies…
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border overflow-hidden">
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
              <div key={i} className="p-5 flex justify-between items-center">
                <div>
                  <p className="font-semibold">{sev.label}</p>
                  <p className="text-xs font-mono text-slate-500">
                    {a.mac}
                  </p>
                  {a.bandwidth_kbps != null && (
                    <p className="text-xs text-slate-500 flex items-center gap-1 mt-1">
                      <TrendingUp className="w-3 h-3" />
                      {(a.bandwidth_kbps / 1000).toFixed(2)} Mbps
                    </p>
                  )}
                </div>

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
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default AnomalyAlerts;
