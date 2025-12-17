import React, { useState } from 'react';
import { Settings2, CheckCircle, AlertCircle, X, Sparkles } from 'lucide-react';
import apiService from '../services/api';

const PolicyControls = ({ selectedDevice = null, onClose = null }) => {
  const [policyMode, setPolicyMode] = useState('auto');
  const [changingMode, setChangingMode] = useState(false);
  
  const [overrideForm, setOverrideForm] = useState({
    macAddress: selectedDevice?.mac || '',
    bandwidthKbps: selectedDevice?.bandwidth_kbps || 5000,
    priority: selectedDevice?.priority || 2,
    durationSec: 3600,
  });
  
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);

  const handleModeChange = async (mode) => {
    try {
      setChangingMode(true);
      await apiService.setPolicyMode(mode);
      setPolicyMode(mode);
      setMessage({ type: 'success', text: `Policy mode set to: ${mode}` });
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to change policy mode' });
      setTimeout(() => setMessage(null), 3000);
    } finally {
      setChangingMode(false);
    }
  };

  const handleOverrideSubmit = async (e) => {
    e.preventDefault();
    
    try {
      setSubmitting(true);
      await apiService.setDeviceOverride(
        overrideForm.macAddress,
        parseInt(overrideForm.bandwidthKbps),
        parseInt(overrideForm.priority),
        overrideForm.durationSec ? parseInt(overrideForm.durationSec) : null
      );
      
      setMessage({ type: 'success', text: 'Override applied successfully!' });
      setTimeout(() => {
        setMessage(null);
        if (onClose) onClose();
      }, 2000);
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to apply override' });
      setTimeout(() => setMessage(null), 3000);
    } finally {
      setSubmitting(false);
    }
  };

  const handleClearOverride = async () => {
    if (!overrideForm.macAddress) return;
    
    try {
      setSubmitting(true);
      await apiService.clearDeviceOverride(overrideForm.macAddress);
      setMessage({ type: 'success', text: 'Override cleared!' });
      setTimeout(() => {
        setMessage(null);
        if (onClose) onClose();
      }, 2000);
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to clear override' });
      setTimeout(() => setMessage(null), 3000);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="p-6 border-b border-gray-200/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500">
              <Settings2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Policy Controls</h2>
              <p className="text-sm text-gray-600">Configure bandwidth allocation rules</p>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-full transition-colors"
            >
              <X className="w-5 h-5 text-gray-600" />
            </button>
          )}
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Message Banner */}
        {message && (
          <div
            className={`glass-card p-4 flex items-center gap-3 border-l-4 animate-slide-up ${
              message.type === 'success' ? 'border-green-500' : 'border-red-500'
            }`}
          >
            {message.type === 'success' ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-600" />
            )}
            <span className="font-medium text-gray-900">{message.text}</span>
          </div>
        )}

        {/* Global Policy Mode */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-4 h-4 text-purple-600" />
            <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">Global Policy Mode</h3>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {['auto', 'equal', 'manual'].map((mode) => (
              <button
                key={mode}
                onClick={() => handleModeChange(mode)}
                disabled={changingMode}
                className={`p-4 rounded-2xl border-2 text-sm font-medium transition-smooth ${
                  policyMode === mode
                    ? 'border-purple-600 bg-gradient-to-br from-purple-50 to-pink-50'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                } ${changingMode ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="font-semibold capitalize text-gray-900 mb-1">{mode}</div>
                <div className="text-xs text-gray-600">
                  {mode === 'auto' && 'ML-driven allocation'}
                  {mode === 'equal' && '5 Mbps per device'}
                  {mode === 'manual' && 'Use overrides only'}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Device Override Form */}
        <div className="border-t border-gray-200/50 pt-6">
          <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">Device Override</h3>
          <form onSubmit={handleOverrideSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                MAC Address *
              </label>
              <input
                type="text"
                required
                placeholder="00:11:22:33:44:55"
                value={overrideForm.macAddress}
                onChange={(e) => setOverrideForm({ ...overrideForm, macAddress: e.target.value })}
                className="w-full"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Bandwidth (kbps) *
                </label>
                <input
                  type="number"
                  required
                  min="100"
                  max="100000"
                  value={overrideForm.bandwidthKbps}
                  onChange={(e) => setOverrideForm({ ...overrideForm, bandwidthKbps: e.target.value })}
                />
                {overrideForm.bandwidthKbps >= 1000 && (
                  <p className="text-xs text-gray-500 mt-1">
                    ≈ {(overrideForm.bandwidthKbps / 1000).toFixed(1)} Mbps
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Priority *
                </label>
                <select
                  value={overrideForm.priority}
                  onChange={(e) => setOverrideForm({ ...overrideForm, priority: e.target.value })}
                >
                  <option value={1}>High (1)</option>
                  <option value={2}>Medium (2)</option>
                  <option value={3}>Low (3)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Duration (seconds)
              </label>
              <input
                type="number"
                min="60"
                max="86400"
                placeholder="Leave empty for permanent"
                value={overrideForm.durationSec}
                onChange={(e) => setOverrideForm({ ...overrideForm, durationSec: e.target.value })}
              />
              <p className="text-xs text-gray-500 mt-1">
                {overrideForm.durationSec
                  ? `Override will expire after ${Math.floor(overrideForm.durationSec / 60)} minutes`
                  : 'Override will persist until manually cleared'}
              </p>
            </div>

            <div className="flex gap-3 pt-4">
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 btn-pill btn-primary"
              >
                {submitting ? 'Applying...' : 'Apply Override'}
              </button>
              
              <button
                type="button"
                onClick={handleClearOverride}
                disabled={submitting || !overrideForm.macAddress}
                className="btn-pill btn-secondary"
              >
                Clear Override
              </button>
            </div>
          </form>
        </div>

        {/* Help Text */}
        <div className="glass-card p-4 border-l-4 border-blue-500">
          <p className="text-sm text-gray-700">
            <strong className="text-blue-700">💡 Tip:</strong> Device overrides take precedence over ML predictions. Use them to
            manually control bandwidth for specific devices when needed.
          </p>
        </div>
      </div>
    </div>
  );
};

export default PolicyControls;