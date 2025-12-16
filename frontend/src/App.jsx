import React, { useState } from 'react';
import { Wifi, RefreshCw, AlertCircle } from 'lucide-react';
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
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <Wifi className="w-8 h-8 text-blue-600 mr-3" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  WiFi Bandwidth Controller
                </h1>
                <p className="text-sm text-gray-600">
                  ML-powered dynamic bandwidth allocation
                </p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setShowPolicyModal(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
              >
                Policy Settings
              </button>
              
              <button
                onClick={handleResetSystem}
                disabled={resetting}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
              >
                {resetting ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Resetting...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2" />
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
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
          <div
            className={`p-4 rounded-lg border flex items-center ${
              resetMessage.type === 'success'
                ? 'bg-green-50 border-green-200 text-green-800'
                : 'bg-red-50 border-red-200 text-red-800'
            }`}
          >
            <AlertCircle className="w-5 h-5 mr-2" />
            <span className="font-medium">{resetMessage.text}</span>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          {/* System Status */}
          <SystemStatus />

          {/* Bandwidth Chart */}
          <BandwidthChart />

          {/* Two Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Device Table - Spans 2 columns */}
            <div className="lg:col-span-2">
              <DeviceTable onOverride={handleDeviceOverride} />
            </div>

            {/* Anomaly Alerts - Spans 1 column */}
            <div className="lg:col-span-1">
              <AnomalyAlerts />
            </div>
          </div>
        </div>
      </main>

      {/* Policy Modal */}
      {showPolicyModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
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
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between text-sm text-gray-600">
            <p>© 2025 WiFi Bandwidth Controller. SDM College of Engineering & Technology.</p>
            <p>Powered by Machine Learning & Linux Traffic Control</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;