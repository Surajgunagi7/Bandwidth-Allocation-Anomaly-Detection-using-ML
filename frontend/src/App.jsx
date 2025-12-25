import React, { useState } from 'react';
import {
  Wifi,
  Settings2,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Zap,
} from 'lucide-react';

import SystemStatus from '@/components/SystemStatus';
import DeviceTable from '@/components/DeviceTable';
import BandwidthChart from '@/components/BandwidthChart';
import AnomalyAlerts from '@/components/AnomalyAlerts';
import PolicyControls from '@/components/PolicyControls';

import api from '@/services/api';
import { cn } from '@/lib/utils';

const App = () => {
  const [showPolicy, setShowPolicy] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [resetting, setResetting] = useState(false);
  const [message, setMessage] = useState(null);

  const handleOverride = (device) => {
    setSelectedDevice(device);
    setShowPolicy(true);
  };

  const handleReset = async () => {
    const confirmed = window.confirm(
      'Are you sure you want to reset the entire system?\n\n' +
      'This will clear all bandwidth rules, device overrides, and historical data.'
    );

    if (!confirmed) return;

    setResetting(true);
    try {
      await api.resetSystem();
      setMessage({
        type: 'success',
        text: 'System reset successfully. All configurations cleared.',
      });
    } catch (error) {
      console.error('Reset error:', error);
      setMessage({
        type: 'error',
        text: 'Failed to reset system. Please try again.',
      });
    } finally {
      setResetting(false);
      setTimeout(() => setMessage(null), 5000);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-slate-50/50 font-sans">
      {/* Header */}
      <header className="fixed top-0 inset-x-0 bg-white/80 backdrop-blur-md border-b border-slate-200 z-40">
        <div className="max-w-[1600px] mx-auto px-6 lg:px-10 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="p-2.5 rounded-xl bg-gradient-to-br from-blue-600 via-indigo-600 to-violet-600 shadow-lg">
                <Wifi className="w-6 h-6 text-white" />
              </div>
              <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-emerald-500 rounded-full border-2 border-white animate-pulse" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">
                WiFi Bandwidth Controller
              </h1>
              <p className="text-xs text-slate-500 flex items-center gap-1.5">
                <Zap className="w-3 h-3 text-amber-500" />
                ML-Powered Traffic Management
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setSelectedDevice(null);
                setShowPolicy(true);
              }}
              className="px-4 py-2.5 bg-white border border-slate-200 hover:bg-blue-50 rounded-xl flex items-center gap-2"
            >
              <Settings2 className="w-4 h-4" />
              <span className="hidden sm:inline">Policy Controls</span>
            </button>

            <button
              onClick={handleReset}
              disabled={resetting}
              className="px-4 py-2.5 bg-gradient-to-r from-rose-500 to-red-600 text-white rounded-xl flex items-center gap-2 disabled:opacity-50"
            >
              <RefreshCw
                className={cn('w-4 h-4', resetting && 'animate-spin')}
              />
              <span className="hidden sm:inline">
                {resetting ? 'Resetting…' : 'System Reset'}
              </span>
            </button>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <RefreshCw className="w-3 h-3 animate-spin" />
              Updating
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-[1600px] pt-28 pb-24 px-6 lg:px-10 space-y-8">
        {message && (
          <div
            className={cn(
              'p-4 rounded-xl border flex items-center gap-4',
              message.type === 'success'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                : 'bg-red-50 border-red-200 text-red-900'
            )}
          >
            {message.type === 'success' ? (
              <CheckCircle className="w-6 h-6 text-emerald-600" />
            ) : (
              <AlertCircle className="w-6 h-6 text-red-600" />
            )}
            <p className="flex-1 font-semibold">{message.text}</p>
            <button
              onClick={() => setMessage(null)}
              className="opacity-60 hover:opacity-100"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}

        <SystemStatus />

        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            <BandwidthChart />
          </div>
          <AnomalyAlerts />
        </div>

        <DeviceTable onOverride={handleOverride} />
      </main>

      {/* Footer */}
      <footer className="fixed bottom-0 inset-x-0 bg-white/80 backdrop-blur-md border-t border-slate-200">
        <div className="max-w-[1600px] mx-auto px-6 lg:px-10 py-3 flex justify-between text-xs sm:text-sm">
          <span className="text-slate-500">
            © 2025 WiFi Bandwidth Controller
          </span>
          <span className="flex items-center gap-2 text-emerald-700 font-semibold">
            <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
            System Operational
          </span>
        </div>
      </footer>

      {showPolicy && (
        <PolicyControls
          selectedDevice={selectedDevice}
          onClose={() => {
            setShowPolicy(false);
            setSelectedDevice(null);
          }}
        />
      )}
    </div>
  );
};

const X = ({ className }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <path d="M18 6 6 18" />
    <path d="m6 6 18 18" />
  </svg>
);

export default App;
