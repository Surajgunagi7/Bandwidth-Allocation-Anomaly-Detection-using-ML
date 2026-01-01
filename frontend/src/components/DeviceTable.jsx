import React, { useEffect, useState } from 'react';
import {
  Cpu,
  AlertTriangle,
  Settings,
  Laptop,
  Smartphone,
  Tv,
  Wifi,
  RefreshCcw,
} from 'lucide-react';

import { cn } from '@/lib/utils';

const DeviceTable = ({ devices, error, onOverride }) => {

  const getDeviceIcon = () => {
    return Wifi;
  };

  return (
    <div className="bg-white rounded-xl border overflow-hidden">
      <div className="p-6 border-b bg-slate-50">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-blue-600 text-white">
            <Cpu className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold">Connected Devices</h2>
            <p className="text-sm text-slate-500">
              {devices.length} device{devices.length !== 1 ? 's' : ''} active
            </p>
          </div>
        </div>
      </div>
      {error && (
        <div className="px-6 py-3 text-sm text-black-700 bg-white border-b flex items-center gap-2">
          <RefreshCcw className="w-4 h-4" />
          Updating...
        </div>
      )}

      <div className="divide-y">
        {devices.length === 0 ? (
          <div className="p-10 text-center text-slate-500">
            No active devices
          </div>
        ) : (
          devices.map((device) => {
            const Icon = getDeviceIcon();
            const isAnomaly = Boolean(device.is_anomaly);

            return (
              <div key={device.mac} className="p-6 flex justify-between items-start">
                <div className="flex gap-4">
                  <div
                    className={cn(
                      'p-3 rounded-lg border',
                      isAnomaly
                        ? 'bg-red-50 border-red-200 text-red-600'
                        : 'bg-white border-slate-200 text-slate-500'
                    )}
                  >
                    <Icon className="w-6 h-6" />
                  </div>

                  <div>
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold text-slate-900">
                        Device {device.mac.slice(-5)}
                      </h3>

                      {isAnomaly && (
                        <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-red-100 text-red-700 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          Anomaly
                        </span>
                      )}

                    </div>

                    <p className="text-xs font-mono text-slate-500">
                      {device.mac}
                    </p>

                    <div className="flex gap-8 mt-3">
                      <div>
                        <p className="text-xs text-slate-400">Allocated Bandwidth</p>
                        {device.bandwidth_kbps != null && (
                            <p className="font-mono font-bold">
                              {(device.bandwidth_kbps / 1000).toFixed(2)} Mbps
                            </p>
                          )}
                      </div>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => onOverride(device)}
                  className="px-4 py-2 text-sm border rounded-lg hover:bg-blue-50 flex items-center gap-2"
                >
                  <Settings className="w-4 h-4" />
                  Configure
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default DeviceTable;
