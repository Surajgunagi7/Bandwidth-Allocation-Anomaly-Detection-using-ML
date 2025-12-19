import React, { useState } from 'react';
import { Wifi, Settings2, RefreshCw, AlertCircle, CheckCircle, Zap, LayoutDashboard } from 'lucide-react';
import SystemStatus from '@/components/SystemStatus';
import DeviceTable from '@/components/DeviceTable';
import BandwidthChart from '@/components/BandwidthChart';
import AnomalyAlerts from '@/components/AnomalyAlerts';
import PolicyControls from '@/components/PolicyControls';
import api from '@/services/api';

const Dashboard = () => {
  const [showPolicy, setShowPolicy] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [resetting, setResetting] = useState(false);
  const [message, setMessage] = useState(null);

  const handleOverride = (device) => {
    setSelectedDevice(device);
    setShowPolicy(true);
  };

  const handleReset = async () => {
    if (!window.confirm('Are you sure you want to reset the entire system?\n\nThis will clear all bandwidth rules, device overrides, and historical data. The system will return to its default state.')) {
      return;
    }

    setResetting(true);
    try {
      await api.resetSystem();
      setMessage({ type: 'success', text: 'System reset successfully! All configurations cleared.' });
    } catch (error) {
      console.error('Reset error:', error);
      setMessage({ type: 'error', text: 'Failed to reset system. Please try again.' });
    } finally {
      setResetting(false);
      setTimeout(() => setMessage(null), 5000);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-slate-50/50 font-sans">
      {/* Fixed Premium Header */}
      <header className="fixed top-0 left-0 right-0 w-full bg-white/80 backdrop-blur-md shadow-sm border-b border-slate-200/60 z-40 transition-all duration-300">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            {/* Logo Section */}
            <div className="flex items-center gap-4 flex-1">
              <div className="relative group cursor-pointer">
                <div className="p-2.5 rounded-xl bg-linear-to-br from-blue-600 via-indigo-600 to-violet-600 shadow-lg shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition-all duration-300 group-hover:scale-105">
                  <Wifi className="w-6 h-6 text-white" />
                </div>
                <div className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-emerald-500 rounded-full border-[3px] border-white animate-pulse"></div>
              </div>
              <div>
                <h1 className="text-xl font-bold font-display bg-clip-text text-transparent bg-linear-to-r from-slate-900 via-slate-800 to-slate-900 tracking-tight">
                  WiFi Bandwidth Controller
                </h1>
                <p className="text-xs text-slate-500 font-medium flex items-center gap-1.5 mt-0.5">
                  <Zap className="w-3 h-3 text-amber-500 fill-amber-500" />
                  ML-Powered Traffic Management
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  setSelectedDevice(null);
                  setShowPolicy(true);
                }}
                className="px-4 py-2.5 bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50 text-slate-700 hover:text-blue-700 font-medium rounded-xl shadow-sm hover:shadow transition-all duration-300 flex items-center gap-2 group"
              >
                <Settings2 className="w-4 h-4 group-hover:rotate-90 transition-transform duration-500" />
                <span className="hidden sm:inline">Policy Controls</span>
              </button>

              <button
                onClick={handleReset}
                disabled={resetting}
                className="px-4 py-2.5 bg-linear-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700 text-white font-medium rounded-xl shadow-lg hover:shadow-xl hover:shadow-red-500/20 transition-all hover:-translate-y-0.5 active:scale-95 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw className={cn("w-4 h-4", resetting ? 'animate-spin' : '')} />
                <span className="hidden sm:inline">{resetting ? 'Resetting...' : 'System Reset'}</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 w-full max-w-7xl mx-auto pt-28 pb-24 px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* Global Message Banner */}
        {message && (
          <div className={cn(
            "p-4 rounded-xl border flex items-center gap-4 shadow-sm animate-in slide-in-from-top-4 duration-300",
            message.type === 'success'
              ? 'bg-emerald-50/80 border-emerald-200 text-emerald-900'
              : 'bg-red-50/80 border-red-200 text-red-900'
          )}>
            {message.type === 'success' ? (
              <CheckCircle className="w-6 h-6 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-6 h-6 text-red-600 shrink-0" />
            )}
            <div className="flex-1">
              <p className="font-semibold">{message.text}</p>
            </div>
            <button
              onClick={() => setMessage(null)}
              className="p-1.5 hover:bg-black/5 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 opacity-50" />
            </button>
          </div>
        )}

        {/* System Status Section */}
        <section className="animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
          <SystemStatus />
        </section>

        {/* Charts and Alerts Grid */}
        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-200">
            <BandwidthChart />
          </div>
          <div className="lg:col-span-1 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-300">
            <AnomalyAlerts />
          </div>
        </div>

        {/* Connected Devices Section */}
        <section className="animate-in fade-in slide-in-from-bottom-4 duration-500 delay-400">
          <DeviceTable onOverride={handleOverride} />
        </section>
      </main>

      {/* Fixed Footer */}
      <footer className="fixed bottom-0 left-0 right-0 w-full bg-white/80 backdrop-blur-md border-t border-slate-200 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-center justify-between text-xs sm:text-sm">
            <p className="text-slate-500 font-medium">
              © 2025 WiFi Bandwidth Controller — Powered by Replit
            </p>
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-50 rounded-full border border-emerald-100">
              <div className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </div>
              <span className="text-emerald-700 font-semibold text-xs uppercase tracking-wide">System Operational</span>
            </div>
          </div>
        </div>
      </footer>

      {/* Policy Controls Modal */}
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

// Simple Close Icon component for the banner
const X = ({ className }) => (
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    width="24" 
    height="24" 
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

export default Dashboard;
