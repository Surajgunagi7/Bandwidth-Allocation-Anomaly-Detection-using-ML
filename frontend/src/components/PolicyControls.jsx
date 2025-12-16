import React, { useState } from 'react';
import { Settings, AlertCircle, CheckCircle, X } from 'lucide-react';
import apiService from '../services/api';

const PolicyControls = ({ selectedDevice = null, onClose = null }) => {
  const [policyMode, setPolicyMode] = useState('auto');
  const [changingMode, setChangingMode] = useState(false);
  
  // Override form state
  const [overrideForm, setOverrideForm] = useState({
    macAddress: selectedDevice?.mac || '',
    bandwidthKbps: selectedDevice?.bandwidth_kbps || 5000,
    priority: selectedDevice?.priority || 2,
    durationSec: 3600, // 1 hour default
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
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <Settings className="w-5 h-5 text-gray-600 mr-2" />
            <h2 className="text-xl font-semibold text-gray-900">Policy Controls</h2>
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
            className={`p-4 rounded-lg border flex items-center ${
              message.type === 'success'
                ? 'bg-green-50 border-green-200 text-green-800'
                : 'bg-red-50 border-red-200 text-red-800'
            }`}
          >
            {message.type === 'success' ? (
              <CheckCircle className="w-5 h-5 mr-2" />
            ) : (
              <AlertCircle className="w-5 h-5 mr-2" />
            )}
            <span className="font-medium">{message.text}</span>
          </div>
        )}

        {/* Global Policy Mode */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-3">Global Policy Mode</h3>
          <div className="grid grid-cols-3 gap-3">
            {['auto', 'equal', 'manual'].map((mode) => (
              <button
                key={mode}
                onClick={() => handleModeChange(mode)}
                disabled={changingMode}
                className={`px-4 py-3 rounded-lg border-2 text-sm font-medium transition-all ${
                  policyMode === mode
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
                } ${changingMode ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="capitalize">{mode}</div>
                <div className="text-xs mt-1 text-gray-500">
                  {mode === 'auto' && 'ML-driven allocation'}
                  {mode === 'equal' && '5 Mbps per device'}
                  {mode === 'manual' && 'Use overrides only'}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Device Override Form */}
        <div className="border-t pt-6">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Device Override</h3>
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
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">
                  {overrideForm.bandwidthKbps >= 1000
                    ? `≈ ${(overrideForm.bandwidthKbps / 1000).toFixed(1)} Mbps`
                    : ''}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Priority *
                </label>
                <select
                  value={overrideForm.priority}
                  onChange={(e) => setOverrideForm({ ...overrideForm, priority: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1">
                {overrideForm.durationSec
                  ? `Override will expire after ${Math.floor(overrideForm.durationSec / 60)} minutes`
                  : 'Override will persist until manually cleared'}
              </p>
            </div>

            <div className="flex space-x-3 pt-4">
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Applying...' : 'Apply Override'}
              </button>
              
              <button
                type="button"
                onClick={handleClearOverride}
                disabled={submitting || !overrideForm.macAddress}
                className="px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Clear Override
              </button>
            </div>
          </form>
        </div>

        {/* Help Text */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">
            <strong>Tip:</strong> Device overrides take precedence over ML predictions. Use them to
            manually control bandwidth for specific devices when needed.
          </p>
        </div>
      </div>
    </div>
  );
};

export default PolicyControls;