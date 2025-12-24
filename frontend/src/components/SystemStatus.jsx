import React, { useEffect, useState } from 'react';
import { Wifi, Activity, HardDrive, Zap, RefreshCw } from 'lucide-react';
import api from '@/services/api';
import { cn } from '@/lib/utils';

const SystemStatus = () => {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [s, h] = await Promise.all([
        api.getStats(),
        api.getHealth()
      ]);
      setStats(s);
      setHealth(h);
    } catch (e) {
      console.error('Status fetch failed', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 5000);
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
        <p className="text-xs uppercase text-slate-500 font-semibold">{label}</p>
        <p className="text-2xl font-bold">{value}</p>
      </div>
      <Icon className="w-8 h-8 text-slate-400" />
    </div>
  );

  if (!stats) return null;

  return (
    <div className="space-y-6 relative">
      {loading && (
        <div className="absolute inset-0 bg-white/50 flex items-center justify-center z-10">
          <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
        </div>
      )}

      {/* Health */}
      <div className={cn(
        'p-5 rounded-xl border-l-4 flex justify-between items-center',
        healthy ? 'border-emerald-500 bg-emerald-50'
                : 'border-red-500 bg-red-50'
      )}>
        <div>
          <p className="font-bold">System Status</p>
          <p className={healthy ? 'text-emerald-700' : 'text-red-700'}>
            {healthy ? 'All systems operational' : 'Service degraded'}
          </p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-2 text-sm font-medium">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card label="Active Devices" value={stats.active_devices} icon={Wifi} />
        <Card label="Bandwidth (Mbps)" value={stats.total_bandwidth_mbps} icon={Activity} />
        <Card label="Pending Uploads" value={stats.uploads_pending} icon={HardDrive} />
        <Card label="Uptime" value={formatUptime(stats.uptime)} icon={Zap} />
      </div>
    </div>
  );
};

export default SystemStatus;
