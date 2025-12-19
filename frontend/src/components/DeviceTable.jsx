import React, { useState, useEffect } from 'react';
import { Cpu, AlertTriangle, Settings, Laptop, Smartphone, Tv, Wifi } from 'lucide-react';
import api from '../services/api';

const DeviceTable = ({ onOverride }) => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDevices = async () => {
    try {
      const data = await api.getDevices();
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

  const getPriorityColor = (priority) => {
    const colors = {
      1: 'bg-emerald-100 text-emerald-700 border-emerald-200',
      2: 'bg-amber-100 text-amber-700 border-amber-200',
      3: 'bg-red-100 text-red-700 border-red-200',
    };
    return colors[priority] || 'bg-slate-100 text-slate-700 border-slate-200';
  };

  const getPriorityLabel = (priority) => {
    const labels = { 1: 'High', 2: 'Medium', 3: 'Low' };
    return labels[priority] || 'Unknown';
  };

  const getDeviceIcon = (hostname) => {
    const lower = hostname.toLowerCase();
    if (lower.includes('iphone') || lower.includes('android') || lower.includes('phone')) return Smartphone;
    if (lower.includes('tv')) return Tv;
    if (lower.includes('macbook') || lower.includes('laptop') || lower.includes('pc')) return Laptop;
    return Wifi;
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 h-64 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-10 h-10">
            <div className="absolute inset-0 border-4 border-slate-100 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-transparent border-t-blue-500 rounded-full animate-spin"></div>
          </div>
          <p className="text-slate-500 font-medium text-sm">Loading connected devices...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 rounded-xl p-6 border border-red-200 shadow-sm">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-6 h-6 text-red-600 shrink-0" />
          <p className="text-red-700 font-semibold text-lg">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden hover:shadow-md transition-shadow relative">
      {loading && (
        <div className="absolute inset-0 bg-white/40 backdrop-blur-sm rounded-lg flex items-center justify-center z-10 pointer-events-none">
          <div className="flex flex-col items-center gap-3">
            <div className="relative w-12 h-12">
              <div className="absolute inset-0 border-4 border-slate-100 rounded-full"></div>
              <div className="absolute inset-0 border-4 border-transparent border-t-blue-500 rounded-full animate-spin"></div>
            </div>
            <p className="text-slate-600 font-medium text-sm">Updating devices...</p>
          </div>
        </div>
      )}
      {/* Header */}
      <div className="p-8 border-b border-slate-200 bg-linear-to-r from-slate-50 to-slate-100/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-linear-to-br from-blue-500 to-blue-600 shadow-lg shadow-blue-500/20">
              <Cpu className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-bold font-display text-slate-900">Connected Devices</h2>
              <p className="text-sm text-slate-500 mt-1 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                {devices.length} device{devices.length !== 1 ? 's' : ''} online
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Devices List */}
      <div className="divide-y divide-slate-100">
        {devices.length === 0 ? (
          <div className="p-12 text-center">
            <div className="bg-slate-50 rounded-full p-6 inline-block mb-4">
              <Cpu className="w-12 h-12 text-slate-300" />
            </div>
            <p className="text-slate-500 font-medium">No devices connected</p>
            <p className="text-xs text-slate-400 mt-1">Connected devices will appear here automatically</p>
          </div>
        ) : (
          devices.map((device, index) => {
            const Icon = getDeviceIcon(device.hostname);
            return (
              <div key={index} className="p-6 hover:bg-slate-50/80 transition-colors group">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex-1 flex items-start gap-4">
                    <div className="p-3 bg-white border border-slate-200 rounded-lg shrink-0 text-slate-500 group-hover:text-blue-500 group-hover:border-blue-200 transition-colors">
                      <Icon className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                        {device.hostname || 'Unknown Device'}
                      </h3>
                      <p className="text-xs text-slate-500 font-mono mt-0.5 flex items-center gap-2">
                        {device.mac_address}
                        <span className="text-slate-300">•</span>
                        {device.ip_address}
                      </p>
                      
                      <div className="flex gap-6 mt-3">
                        <div>
                          <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold mb-0.5">Bandwidth</p>
                          <p className="text-sm font-bold font-mono text-slate-700">
                            {device.bandwidth_kbps ? (device.bandwidth_kbps / 1000).toFixed(2) : '0'} Mbps
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold mb-0.5">Priority</p>
                          <span className={cn("inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase border", getPriorityColor(device.priority))}>
                            {getPriorityLabel(device.priority)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => onOverride(device)}
                    className="px-4 py-2 bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 hover:border-blue-200 rounded-lg text-sm font-medium transition-all flex items-center gap-2 shadow-sm hover:shadow active:scale-95"
                  >
                    <Settings className="w-4 h-4" />
                    Configure
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default DeviceTable;
