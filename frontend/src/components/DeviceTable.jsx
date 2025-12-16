import React, { useState, useEffect } from 'react';
import { Monitor, AlertTriangle, TrendingUp, Settings, X } from 'lucide-react';
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
    const interval = setInterval(fetchDevices, 3000); // Refresh every 3s
    return () => clearInterval(interval);
  }, []);

  const getPriorityLabel = (priority) => {
    const labels = { 1: 'High', 2: 'Medium', 3: 'Low' };
    return labels[priority] || 'Unknown';
  };

  const getPriorityColor = (priority) => {
    const colors = {
      1: 'bg-green-100 text-green-800 border-green-200',
      2: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      3: 'bg-red-100 text-red-800 border-red-200',
    };
    return colors[priority] || 'bg-gray-100 text-gray-800 border-gray-200';
  };

  const getTrafficClassIcon = (trafficClass) => {
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
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-12 bg-gray-200 rounded"></div>
          <div className="h-12 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="text-red-600">{error}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">Active Devices</h2>
          <span className="text-sm text-gray-600">{devices.length} devices</span>
        </div>
      </div>

      {devices.length === 0 ? (
        <div className="p-12 text-center">
          <Monitor className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">No active devices</p>
          <p className="text-sm text-gray-500 mt-2">Devices will appear here once traffic is detected</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Device
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Traffic Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Bandwidth
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Priority
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {devices.map((device) => (
                <tr key={device.mac} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <Monitor className="w-5 h-5 text-gray-400 mr-3" />
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {device.mac}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <span className="mr-2">{getTrafficClassIcon(device.traffic_class)}</span>
                      <span className="text-sm text-gray-900 capitalize">
                        {device.traffic_class?.replace('_', ' ') || 'Unknown'}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <TrendingUp className="w-4 h-4 text-blue-500 mr-2" />
                      <span className="text-sm font-medium text-gray-900">
                        {formatBandwidth(device.bandwidth_kbps)}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full border ${getPriorityColor(device.priority)}`}>
                      {getPriorityLabel(device.priority)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {device.is_anomaly ? (
                      <div className="flex items-center text-red-600">
                        <AlertTriangle className="w-4 h-4 mr-1" />
                        <span className="text-xs font-medium">Anomaly</span>
                      </div>
                    ) : (
                      <span className="text-xs text-green-600 font-medium">Normal</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => handleOverrideClick(device)}
                      className="text-blue-600 hover:text-blue-900 inline-flex items-center"
                      title="Set Override"
                    >
                      <Settings className="w-4 h-4 mr-1" />
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