import React, { useState, useEffect } from 'react';
import { Monitor, AlertTriangle, TrendingUp, Settings, Cpu } from 'lucide-react';
import apiService from '../services/api';

const DeviceTable = ({ onOverride }) => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDevices = async () => {
    try {
      const data = await apiService.getDevices();
      setDevices(data.devices || []);
      setError(null);
    } catch (err) {
      setError('Failed to fetch devices');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
    const interval = setInterval(fetchDevices, 3000);
    return () => clearInterval(interval);
  }, []);

  const getPriorityLabel = (priority) => {
    const labels = { 1: 'High', 2: 'Medium', 3: 'Low' };
    return labels[priority] || 'Unknown';
  };

  const getPriorityBadge = (priority) => {
    const badges = {
      1: 'badge-success',
      2: 'badge-warning', 
      3: 'badge-error',
    };
    return badges[priority] || 'badge-info';
  };

  const getTrafficIcon = (trafficClass) => {
    const icons = {
      'video_conference': '🎥',
      'video': '📹',
      'voip': '📞',
      'streaming': '🎬',
      'web': '🌐',
      'bulk': '📦',
      'file_transfer': '📁',
      'unknown': '❓',
    };
    return icons[trafficClass] || '❓';
  };

  const formatBandwidth = (kbps) => {
    if (kbps >= 1000) {
      return `${(kbps / 1000).toFixed(1)} Mbps`;
    }
    return `${kbps} kbps`;
  };

  const handleOverrideClick = (device) => {
    if (onOverride) {
      onOverride(device);
    }
  };

  if (loading) {
    return (
      <div className="glass-card p-8">
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="loading-shimmer h-16 rounded-2xl"></div>
          ))}
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

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-gray-200/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500">
              <Cpu className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Active Devices</h2>
              <p className="text-sm text-gray-600">{devices.length} devices connected</p>
            </div>
          </div>
        </div>
      </div>

      {devices.length === 0 ? (
        <div className="p-16 text-center">
          <div className="inline-flex p-4 rounded-full bg-gray-100 mb-4">
            <Monitor className="w-12 h-12 text-gray-400" />
          </div>
          <p className="text-gray-600 font-medium mb-2">No active devices</p>
          <p className="text-sm text-gray-500">Devices will appear here once traffic is detected</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Device
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Traffic Type
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Bandwidth
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Priority
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-4 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device, index) => (
                <tr key={device.mac} className="transition-smooth hover:bg-white/50" style={{ animationDelay: `${index * 0.05}s` }}>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500">
                        <Monitor className="w-4 h-4 text-white" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-gray-900">{device.mac}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{getTrafficIcon(device.traffic_class)}</span>
                      <span className="text-sm font-medium text-gray-700 capitalize">
                        {device.traffic_class?.replace('_', ' ') || 'Unknown'}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-purple-600" />
                      <span className="text-sm font-bold text-gray-900">
                        {formatBandwidth(device.bandwidth_kbps)}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`badge-pill ${getPriorityBadge(device.priority)}`}>
                      {getPriorityLabel(device.priority)}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {device.is_anomaly ? (
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-red-600" />
                        <span className="badge-pill badge-error !text-xs">Anomaly</span>
                      </div>
                    ) : (
                      <span className="badge-pill badge-success !text-xs">Normal</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => handleOverrideClick(device)}
                      className="btn-pill btn-secondary !py-2 !px-4 !text-xs"
                    >
                      <Settings className="w-3 h-3" />
                      Override
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default DeviceTable;