import React, { useState } from 'react';
import { Wifi, RefreshCw, Settings2, Sparkles } from 'lucide-react';
import SystemStatus from './components/SystemStatus';
import DeviceTable from './components/DeviceTable';
import AnomalyAlerts from './components/AnomalyAlerts';
import BandwidthChart from './components/BandwidthChart';
import PolicyControls from './components/PolicyControls';
import apiService from './services/api';

function App() {
  const [showPolicyModal, setShowPolicyModal] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [resetting, setResetting] = useState(false);
  const [resetMessage, setResetMessage] = useState(null);

  const handleDeviceOverride = (device) => {
    setSelectedDevice(device);
    setShowPolicyModal(true);
  };

  const handleResetSystem = async () => {
    if (!window.confirm('Are you sure you want to reset the entire system? This will clear all TC rules and history.')) {
      return;
    }

    try {
      setResetting(true);
      await apiService.resetSystem();
      setResetMessage({ type: 'success', text: 'System reset successfully!' });
      setTimeout(() => setResetMessage(null), 3000);
    } catch (err) {
      setResetMessage({ type: 'error', text: 'Failed to reset system' });
      setTimeout(() => setResetMessage(null), 3000);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="min-h-screen">
      {/* Glassmorphic Header */}
      <header className="glass sticky top-0 z-50 border-b border-white/20">
        <div className="max-w-[1400px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo & Title */}
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-pink-600 rounded-2xl blur-lg opacity-50"></div>
                <div className="relative bg-white/90 p-3 rounded-2xl">
                  <Wifi className="w-7 h-7 text-purple-600" />
                </div>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gradient flex items-center gap-2">
                  WiFi Controller
                  <Sparkles className="w-5 h-5" />
                </h1>
                <p className="text-sm text-gray-600 font-medium">
                  ML-powered bandwidth allocation
                </p>
              </div>
            </div>
            
            {/* Action Buttons */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowPolicyModal(true)}
                className="btn-pill btn-secondary"
              >
                <Settings2 className="w-4 h-4" />
                Policy Settings
              </button>
              
              <button
                onClick={handleResetSystem}
                disabled={resetting}
                className="btn-pill btn-danger"
              >
                {resetting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Resetting...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    Reset System
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Reset Message */}
      {resetMessage && (
        <div className="max-w-[1400px] mx-auto px-6 mt-6 animate-slide-up">
          <div className={`glass-card p-4 flex items-center gap-3 ${
            resetMessage.type === 'success' ? 'border-l-4 border-green-500' : 'border-l-4 border-red-500'
          }`}>
            <div className={`w-2 h-2 rounded-full ${
              resetMessage.type === 'success' ? 'bg-green-500' : 'bg-red-500'
            } animate-pulse`}></div>
            <span className="font-medium text-gray-800">{resetMessage.text}</span>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-[1400px] mx-auto px-6 py-8">
        <div className="space-y-8">
          {/* System Status */}
          <div className="animate-slide-up">
            <SystemStatus />
          </div>

          {/* Bandwidth Chart */}
          <div className="animate-slide-up" style={{ animationDelay: '0.1s' }}>
            <BandwidthChart />
          </div>

          {/* Two Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Device Table - Spans 2 columns */}
            <div className="lg:col-span-2 animate-slide-up" style={{ animationDelay: '0.2s' }}>
              <DeviceTable onOverride={handleDeviceOverride} />
            </div>

            {/* Anomaly Alerts - Spans 1 column */}
            <div className="lg:col-span-1 animate-slide-up" style={{ animationDelay: '0.3s' }}>
              <AnomalyAlerts />
            </div>
          </div>
        </div>
      </main>

      {/* Policy Modal with Backdrop */}
      {showPolicyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 modal-overlay animate-fade-in">
          <div className="glass-card max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-slide-up">
            <PolicyControls
              selectedDevice={selectedDevice}
              onClose={() => {
                setShowPolicyModal(false);
                setSelectedDevice(null);
              }}
            />
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="glass mt-16 border-t border-white/20">
        <div className="max-w-[1400px] mx-auto px-6 py-6">
          <div className="flex items-center justify-between text-sm text-gray-600">
            <p className="font-medium">© 2025 WiFi Bandwidth Controller • SDM College of Engineering & Technology</p>
            <p className="flex items-center gap-2">
              Powered by <span className="text-gradient font-semibold">Machine Learning</span>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;