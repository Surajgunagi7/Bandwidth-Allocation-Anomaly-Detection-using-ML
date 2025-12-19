import React, { useState } from 'react';
import { Wifi, Settings2, RefreshCw, AlertCircle, CheckCircle, Zap } from 'lucide-react';
import SystemStatus from './components/SystemStatus';
import DeviceTable from './components/DeviceTable';
import BandwidthChart from './components/BandwidthChart';
import AnomalyAlerts from './components/AnomalyAlerts';
import PolicyControls from './components/PolicyControls';

// Error Boundary Component
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 bg-red-50 border-2 border-red-300 rounded-xl">
          <div className="flex items-start gap-4">
            <AlertCircle className="w-6 h-6 text-red-600 mt-1 shrink-0" />
            <div>
              <h3 className="font-bold text-red-900 mb-2">Component Error</h3>
              <p className="text-red-800 text-sm mb-3">{this.state.error?.message}</p>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700"
              >
                Reload Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

function App() {
  const [showPolicy, setShowPolicy] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [resetting, setResetting] = useState(false);
  const [message, setMessage] = useState(null);

  const apiBaseURL = 'http://localhost:8000';

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
      const response = await fetch(`${apiBaseURL}/api/reset`, {
        method: 'POST'
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: 'System reset successfully! All configurations cleared.' });
      } else {
        throw new Error('Reset failed');
      }
    } catch (error) {
      console.error('Reset error:', error);
      setMessage({ type: 'error', text: 'Failed to reset system. Please try again.' });
    } finally {
      setResetting(false);
      setTimeout(() => setMessage(null), 5000);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-linear-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Fixed Premium Header */}
      <header className="fixed top-0 left-0 right-0 w-full bg-white/95 backdrop-blur-md shadow-lg border-b border-slate-200 z-50">
        <div className="px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            {/* Logo Section */}
            <div className="flex items-center gap-4 flex-1">
              <div className="relative">
                <div className="p-3 rounded-2xl bg-linear-to-br from-blue-600 via-indigo-600 to-purple-600 shadow-xl">
                  <Wifi className="w-7 h-7 text-white" />
                </div>
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-white animate-pulse"></div>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-linear-to-r from-blue-600 to-indigo-600">
                  WiFi Bandwidth Controller
                </h1>
                <p className="text-sm text-slate-600 font-medium flex items-center gap-2 mt-1">
                  <Zap className="w-3.5 h-3.5 text-yellow-500" />
                  ML-Powered Intelligent Traffic Management
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowPolicy(true)}
                className="px-5 py-3 bg-linear-to-r from-blue-500 via-indigo-500 to-purple-600 hover:from-blue-600 hover:via-indigo-600 hover:to-purple-700 text-white font-bold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 flex items-center gap-2"
              >
                <Settings2 className="w-5 h-5" />
                <span className="hidden sm:inline">Policy Controls</span>
              </button>

              <button
                onClick={handleReset}
                disabled={resetting}
                className="px-5 py-3 bg-linear-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700 text-white font-bold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw className={`w-5 h-5 ${resetting ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">{resetting ? 'Resetting...' : 'Reset'}</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto pt-32 pb-24 w-full">
        <div className="px-4 sm:px-6 lg:px-8 py-12 space-y-12">
          {/* Global Message Banner */}
          {message && (
            <div className={`p-5 rounded-2xl border-2 flex items-center gap-4 shadow-lg ${
              message.type === 'success'
                ? 'bg-linear-to-r from-green-50 to-emerald-50 border-green-300'
                : 'bg-linear-to-r from-red-50 to-rose-50 border-red-300'
            }`}>
              {message.type === 'success' ? (
                <CheckCircle className="w-7 h-7 text-green-600 shrink-0" />
              ) : (
                <AlertCircle className="w-7 h-7 text-red-600 shrink-0" />
              )}
              <div className="flex-1">
                <p className={`font-bold text-lg ${
                  message.type === 'success' ? 'text-green-900' : 'text-red-900'
                }`}>
                  {message.text}
                </p>
              </div>
              <button
                onClick={() => setMessage(null)}
                className="p-2 hover:bg-white/50 rounded-lg transition-colors"
              >
                <span className="text-2xl">×</span>
              </button>
            </div>
          )}

          {/* System Status Section */}
          <ErrorBoundary>
            <SystemStatus />
          </ErrorBoundary>

          {/* Charts and Alerts Grid */}
          <div className="grid lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2">
              <ErrorBoundary>
                <BandwidthChart />
              </ErrorBoundary>
            </div>
            <div className="lg:col-span-1">
              <ErrorBoundary>
                <AnomalyAlerts />
              </ErrorBoundary>
            </div>
          </div>

          {/* Connected Devices Section */}
          <ErrorBoundary>
            <DeviceTable onOverride={handleOverride} />
          </ErrorBoundary>
        </div>
      </main>

      {/* Fixed Footer */}
      <footer className="fixed bottom-0 left-0 right-0 w-full bg-white/95 backdrop-blur-md border-t border-slate-200 shadow-lg z-40">
        <div className="px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between text-sm">
            <p className="text-slate-600 font-medium">
              © 2025 WiFi Bandwidth Controller — Powered by Machine Learning
            </p>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-slate-600 font-medium">System Operational</span>
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
}

export default App;