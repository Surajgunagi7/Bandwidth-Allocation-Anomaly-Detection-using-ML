import React, { useState, useEffect } from 'react';
import { Activity, Wifi, HardDrive, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
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
    const interval = setInterval(fetchData, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const StatusCard = ({ title, value, icon: Icon, color = 'blue', suffix = '' }) => (
    <div className="bg-white rounded-lg shadow p-6 border-l-4" style={{ borderLeftColor: `var(--tw-color-${color}-500)` }}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">
            {value}{suffix}
          </p>
        </div>
        <div className={`p-3 bg-${color}-100 rounded-full`}>
          <Icon className={`w-6 h-6 text-${color}-600`} />
        </div>
      </div>
    </div>
  );

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-48">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center">
          <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
          <p className="text-red-800">{error}</p>
        </div>
      </div>
    );
  }

  const isHealthy = health?.status === 'healthy' && health?.worker_thread;

  return (
    <div className="space-y-6">
      {/* System Health Banner */}
      <div className={`${isHealthy ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'} border rounded-lg p-4`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            {isHealthy ? (
              <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
            )}
            <span className={`font-medium ${isHealthy ? 'text-green-800' : 'text-red-800'}`}>
              System Status: {isHealthy ? 'Healthy' : 'Degraded'}
            </span>
          </div>
          <button
            onClick={fetchData}
            className="p-2 hover:bg-gray-200 rounded-full transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatusCard
          title="Active Devices"
          value={stats?.active_devices || 0}
          icon={Wifi}
          color="blue"
        />
        
        <StatusCard
          title="Total Bandwidth"
          value={stats?.total_bandwidth_mbps || 0}
          icon={Activity}
          color="green"
          suffix=" Mbps"
        />
        
        <StatusCard
          title="Pending Uploads"
          value={stats?.uploads_pending || 0}
          icon={HardDrive}
          color="yellow"
        />
        
        <StatusCard
          title="Uptime"
          value={stats?.uptime ? formatUptime(stats.uptime) : 'N/A'}
          icon={CheckCircle}
          color="purple"
        />
      </div>

      {/* Detailed Info */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">System Details</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-gray-600">Interface</p>
            <p className="font-medium text-gray-900">{stats?.ap_interface || 'N/A'}</p>
          </div>
          <div>
            <p className="text-gray-600">Policy Mode</p>
            <p className="font-medium text-gray-900 capitalize">
              {stats?.policy_mode || 'auto'}
            </p>
          </div>
          <div>
            <p className="text-gray-600">Active Overrides</p>
            <p className="font-medium text-gray-900">{stats?.active_overrides || 0}</p>
          </div>
          <div>
            <p className="text-gray-600">Processed Files</p>
            <p className="font-medium text-gray-900">{stats?.processed_total || 0}</p>
          </div>
          <div>
            <p className="text-gray-600">Errors</p>
            <p className="font-medium text-gray-900">{stats?.errors_total || 0}</p>
          </div>
          <div>
            <p className="text-gray-600">Worker Status</p>
            <p className={`font-medium ${stats?.worker_alive ? 'text-green-600' : 'text-red-600'}`}>
              {stats?.worker_alive ? 'Running' : 'Stopped'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemStatus;