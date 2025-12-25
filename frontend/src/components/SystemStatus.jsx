import React, { useEffect, useState } from 'react';
import { Wifi, Activity, HardDrive, Zap, RefreshCw, Shield } from 'lucide-react';
import api from '@/services/api';
import { cn } from '@/lib/utils';

const POLL_INTERVAL_MS = 5000;

const SystemStatus = () => {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async (isInitial = false) => {
    try {
      if (isInitial) setInitialLoading(true);
      else setRefreshing(true);

      const [s, h] = await Promise.all([
        api.getStats(),
        api.getHealth(),
      ]);
      setStats(s);
      setHealth(h);
    } catch (e) {
      console.error('Status fetch failed', e);
    } finally {
      setInitialLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData(true);
    const id = setInterval(() => fetchData(false), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  const healthy = health?.status === 'healthy' && health?.worker_alive;

  const formatUptime = (sec = 0) => {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return `${h}h ${m}m`;
  };

  const Card = ({ label, value, icon: Icon }) => (
    <div className="bg-white rounded-xl border p-6 flex justify-between items-center">
      <div>
        <p className="text-xs uppercase text-slate-500 font-semibold">
          {label}
        </p>
        <p className="text-2xl font-bold">{value}</p>
      </div>
      <Icon className="w-8 h-8 text-slate-400" />
    </div>
  );

  if (!stats) return null;

  return (
    <div className="space-y-6 relative">
      {/* Health banner */}
      <div
        className={cn(
          'p-5 rounded-xl border-l-4 flex justify-between items-center',
          healthy
            ? 'border-emerald-500 bg-emerald-50'
            : 'border-red-500 bg-red-50'
        )}
      >
        <div>
          <p className="font-bold">System Status</p>
          <p className={healthy ? 'text-emerald-700' : 'text-red-700'}>
            {healthy ? 'All systems operational' : 'Service degraded'}
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Policy mode (read-only) */}
          {stats.policy_mode && (
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
              <Shield className="w-4 h-4 text-blue-600" />
              <span className="capitalize">
                Policy: {stats.policy_mode}
              </span>
            </div>
          )}

          <button
            onClick={() => fetchData(false)}
            className="flex items-center gap-2 text-sm font-medium"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card
          label="Active Devices"
          value={stats.active_devices}
          icon={Wifi}
        />
        <Card
          label="Total Bandwidth (Mbps)"
          value={stats.total_bandwidth_mbps}
          icon={Activity}
        />
        <Card
          label="Uptime"
          value={formatUptime(stats.uptime)}
          icon={Zap}
        />
      </div>
    </div>
  );
};

export default SystemStatus;
