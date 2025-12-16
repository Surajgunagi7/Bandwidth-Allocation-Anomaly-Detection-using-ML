import React, { useState, useEffect } from 'react';
import { Activity, Wifi, HardDrive, CheckCircle, RefreshCw, Zap, TrendingUp } from 'lucide-react';
import apiService from '../services/api';

const SystemStatus = () => {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsData, healthData] = await Promise.all([
        apiService.getStats(),
        apiService.getHealth(),
      ]);
      setStats(statsData);
      setHealth(healthData);
      setError(null);
    } catch (err) {
      setError('Failed to fetch system status');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const StatusCard = ({ title, value, icon: Icon, gradient, suffix = '' }) => (
    <div className="glass-card p-6 group">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
          <p className="text-3xl font-bold text-gray-900">
            {value}<span className="text-lg text-gray-600">{suffix}</span>
          </p>
        </div>
        <div className={`relative p-4 rounded-2xl ${gradient} transition-smooth group-hover:scale-110`}>
          <Icon className="w-8 h-8 text-white" />
        </div>
      </div>
    </div>
  );

  if (loading && !stats) {
    return (
      <div className="glass-card p-12 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 animate-spin text-purple-600 mx-auto mb-4" />
          <p className="text-gray-600 font-medium">Loading system status...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card p-6 border-l-4 border-red-500">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse"></div>
          <p className="text-red-800 font-medium">{error}</p>
        </div>
      </div>
    );
  }

  const isHealthy = health?.status === 'healthy' && health?.worker_thread;

  return (
    <div className="space-y-6">
      {/* System Health Banner */}
      <div className={`glass-card p-4 border-l-4 ${isHealthy ? 'border-green-500' : 'border-red-500'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${isHealthy ? 'bg-green-500' : 'bg-red-500'} animate-pulse`}></div>
            <span className={`font-semibold ${isHealthy ? 'text-green-800' : 'text-red-800'}`}>
              System Status: {isHealthy ? 'Healthy' : 'Degraded'}
            </span>
          </div>
          <button
            onClick={fetchData}
            className="btn-pill btn-secondary !py-2 !px-4 !text-xs"
            title="Refresh"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        <StatusCard
          title="Active Devices"
          value={stats?.active_devices || 0}
          icon={Wifi}
          gradient="bg-gradient-to-br from-purple-500 to-pink-500"
        />
        
        <StatusCard
          title="Total Bandwidth"
          value={stats?.total_bandwidth_mbps || 0}
          icon={Activity}
          gradient="bg-gradient-to-br from-blue-500 to-cyan-500"
          suffix=" Mbps"
        />
        
        <StatusCard
          title="Pending Uploads"
          value={stats?.uploads_pending || 0}
          icon={HardDrive}
          gradient="bg-gradient-to-br from-amber-500 to-orange-500"
        />
        
        <StatusCard
          title="System Uptime"
          value={stats?.uptime ? formatUptime(stats.uptime) : 'N/A'}
          icon={Zap}
          gradient="bg-gradient-to-br from-green-500 to-emerald-500"
        />
      </div>

      {/* Detailed Info */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500">
            <TrendingUp className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900">System Details</h3>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Interface</p>
            <p className="font-semibold text-gray-900 text-sm">{stats?.ap_interface || 'N/A'}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Policy Mode</p>
            <span className="badge-pill badge-info">{stats?.policy_mode || 'auto'}</span>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Active Overrides</p>
            <p className="font-semibold text-gray-900 text-sm">{stats?.active_overrides || 0}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Processed Files</p>
            <p className="font-semibold text-gray-900 text-sm">{stats?.processed_total || 0}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Errors</p>
            <p className="font-semibold text-gray-900 text-sm">{stats?.errors_total || 0}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Worker Status</p>
            <span className={`badge-pill ${stats?.worker_alive ? 'badge-success' : 'badge-error'}`}>
              {stats?.worker_alive ? 'Running' : 'Stopped'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemStatus;