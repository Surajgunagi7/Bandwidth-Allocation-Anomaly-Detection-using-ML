import React, { useState, useEffect } from 'react';
import { Wifi, Activity, HardDrive, Zap, RefreshCw } from 'lucide-react';
import api from '../services/api';
import { cn } from '@/lib/utils';

const SystemStatus = () => {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [s, h] = await Promise.all([api.getStats(), api.getHealth()]);
      setStats(s);
      setHealth(h);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 5000);
    return () => clearInterval(id);
  }, []);

  const formatUptime = (sec) => {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return `${h}h ${m}m`;
  };

  const Card = ({ title, value, icon: Icon, gradient, suffix = '' }) => (
    <div className="w-full bg-white/80 backdrop-blur-sm rounded-xl p-8 shadow-sm border border-slate-200 hover:shadow-md transition-shadow h-44 flex flex-col justify-between group">
      <div className="flex justify-between items-start flex-1">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">{title}</p>
          <p className="text-4xl font-display font-bold text-slate-900 mt-3 leading-tight tracking-tight">
            {value}<span className="text-base font-normal text-slate-500 ml-2">{suffix}</span>
          </p>
        </div>
        <div className={cn("p-4 rounded-xl shadow-lg shrink-0 ml-3 transition-transform group-hover:scale-110", gradient)}>
          <Icon className="w-7 h-7 text-white" />
        </div>
      </div>
    </div>
  );

  const stats_display = stats || {
    active_devices: 0,
    total_bandwidth_mbps: 0,
    uploads_pending: 0,
    uptime: 0,
    ap_interface: 'N/A',
    policy_mode: 'auto',
    active_overrides: 0,
    processed_total: 0,
    errors_total: 0,
    worker_alive: false
  };

  const healthy = health?.status === 'healthy' && health?.worker_alive;

  return (
    <div className="space-y-8 w-full relative">
      {loading && (
        <div className="absolute inset-0 bg-white/40 backdrop-blur-sm rounded-xl flex items-center justify-center z-10 pointer-events-none" style={{height: '100%'}}>
          <div className="flex flex-col items-center gap-3">
            <div className="relative w-12 h-12">
              <div className="absolute inset-0 border-4 border-slate-100 rounded-full"></div>
              <div className="absolute inset-0 border-4 border-transparent border-t-blue-500 rounded-full animate-spin"></div>
            </div>
            <p className="text-slate-600 font-medium text-sm">Refreshing...</p>
          </div>
        </div>
      )}
      {/* System Health Card */}
      <div className={cn(
        "w-full bg-white/90 backdrop-blur-md rounded-xl p-8 shadow-sm border-l-4 border border-slate-200 hover:shadow-md transition-all min-h-28 flex items-center",
        healthy ? 'border-l-emerald-500' : 'border-l-red-500'
      )}>
        <div className="flex justify-between items-center w-full">
          <div className="flex items-center gap-5 flex-1">
            <div className={cn("w-4 h-4 rounded-full animate-pulse shadow-lg shrink-0", healthy ? 'bg-emerald-500' : 'bg-red-500')}></div>
            <div className="min-w-0">
              <p className="text-xl font-bold font-display text-slate-900">System Status</p>
              <p className={cn("text-base font-medium", healthy ? 'text-emerald-600' : 'text-red-600')}>
                {healthy ? '✓ All Systems Operational' : '✗ Service Degraded'}
              </p>
            </div>
          </div>
          <button 
            onClick={fetchData} 
            className="px-6 py-3 h-12 bg-slate-900 hover:bg-slate-800 text-white font-medium rounded-lg text-sm transition-all flex items-center gap-2 shrink-0 ml-4 whitespace-nowrap shadow-md hover:shadow-lg active:scale-95"
            title="Refresh Status"
          >
            <RefreshCw className={cn("w-4 h-4", loading ? 'animate-spin' : '')} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card 
          title="Active Devices" 
          value={stats_display.active_devices} 
          icon={Wifi} 
          gradient="bg-gradient-to-br from-blue-500 to-indigo-600" 
        />
        <Card 
          title="Total Bandwidth" 
          value={stats_display.total_bandwidth_mbps} 
          icon={Activity} 
          gradient="bg-gradient-to-br from-violet-500 to-purple-600" 
          suffix=" Mbps" 
        />
        <Card 
          title="Pending Uploads" 
          value={stats_display.uploads_pending} 
          icon={HardDrive} 
          gradient="bg-gradient-to-br from-amber-500 to-orange-600" 
        />
        <Card 
          title="Uptime" 
          value={formatUptime(stats?.uptime || stats_display.uptime)} 
          icon={Zap} 
          gradient="bg-gradient-to-br from-emerald-500 to-teal-600" 
        />
      </div>

      {/* System Details */}
      <div className="w-full bg-white/80 backdrop-blur-sm rounded-xl p-8 shadow-sm border border-slate-200">
        <h3 className="text-lg font-bold font-display text-slate-900 mb-8">System Metrics</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-6">
          {[
            { label: 'Interface', value: stats?.ap_interface || stats_display.ap_interface },
            { label: 'Policy Mode', value: stats?.policy_mode || stats_display.policy_mode, badge: true, type: 'info' },
            { label: 'Overrides', value: stats?.active_overrides || stats_display.active_overrides },
            { label: 'Processed', value: stats?.processed_total || stats_display.processed_total },
            { label: 'Errors', value: stats?.errors_total || stats_display.errors_total },
            { label: 'Worker', value: (stats?.worker_alive ?? stats_display.worker_alive) ? 'Running' : 'Stopped', badge: true, type: (stats?.worker_alive ?? stats_display.worker_alive) ? 'success' : 'error' },
          ].map((item, i) => (
            <div key={i} className="bg-slate-50/50 rounded-lg p-6 text-center hover:bg-slate-50 transition h-28 flex flex-col justify-center border border-slate-200/50">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">{item.label}</p>
              {item.badge ? (
                <span className={cn(
                  "mx-auto inline-block px-3 py-1.5 rounded-full text-xs font-bold whitespace-nowrap border",
                  item.type === 'info' ? 'bg-blue-50 text-blue-700 border-blue-100' : item.type === 'success' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-red-50 text-red-700 border-red-100'
                )}>
                  {item.value}
                </span>
              ) : (
                <p className="text-lg font-bold font-display text-slate-900 truncate">{item.value}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SystemStatus;
