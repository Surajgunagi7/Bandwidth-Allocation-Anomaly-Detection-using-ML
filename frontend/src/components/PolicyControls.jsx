import React, { useState } from 'react';
import { Settings2, CheckCircle, AlertCircle, X, Info, Shield, Zap } from 'lucide-react';
import api from '../services/api';

const PolicyControls = ({ selectedDevice, onClose }) => {
  const [policyMode, setPolicyMode] = useState('auto');
  const [changing, setChanging] = useState(false);
  
  // Use strings for form state to handle input handling better
  const [form, setForm] = useState({
    macAddress: selectedDevice?.mac_address || '',
    bandwidthKbps: String(selectedDevice?.bandwidth_kbps || 5000),
    priority: String(selectedDevice?.priority || 2),
    durationSec: '3600'
  });
  
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);

  const validate = () => {
    const err = {};
    if (!form.macAddress) err.macAddress = 'Required';
    else if (!/^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/.test(form.macAddress))
      err.macAddress = 'Invalid MAC format';

    if (Number(form.bandwidthKbps) < 100) err.bandwidthKbps = 'Min 100 kbps';
    setErrors(err);
    return Object.keys(err).length === 0;
  };

  const changeMode = async (mode) => {
    setChanging(true);
    try {
      await api.setPolicyMode(mode);
      setPolicyMode(mode);
      setMessage({ type: 'success', text: `Policy Mode updated to ${mode.charAt(0).toUpperCase() + mode.slice(1)}` });
    } catch {
      setMessage({ type: 'error', text: 'Failed to change mode' });
    } finally {
      setChanging(false);
      setTimeout(() => setMessage(null), 3000);
    }
  };

  const applyOverride = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      await api.setDeviceOverride(
        form.macAddress, 
        Number(form.bandwidthKbps), 
        Number(form.priority), 
        Number(form.durationSec) || null
      );
      setMessage({ type: 'success', text: 'Device override applied successfully' });
      setTimeout(() => onClose?.(), 1500);
    } catch {
      setMessage({ type: 'error', text: 'Failed to apply override' });
    } finally {
      setSubmitting(false);
      setTimeout(() => setMessage(null), 3000);
    }
  };

  const clearOverride = async () => {
    if (!form.macAddress) return;
    setSubmitting(true);
    try {
      await api.clearDeviceOverride(form.macAddress);
      setMessage({ type: 'success', text: 'Device override cleared' });
      setTimeout(() => onClose?.(), 1500);
    } catch {
      setMessage({ type: 'error', text: 'Failed to clear override' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-in zoom-in-95 duration-200 border border-slate-200">
        <div className="sticky top-0 bg-white/95 backdrop-blur-md border-b border-slate-100 p-8 flex justify-between items-center z-10">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-linear-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/20">
              <Settings2 className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-bold font-display text-slate-900">Policy Controls</h2>
              <p className="text-sm text-slate-500 mt-0.5">Manage bandwidth allocation rules</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-400 hover:text-slate-600">
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="p-8 space-y-8">
          {message && (
            <div className={cn(
              "p-4 rounded-xl border-l-4 flex items-center gap-3 shadow-sm animate-in slide-in-from-top-2",
              message.type === 'success' ? 'bg-emerald-50 border-emerald-500 text-emerald-700' : 'bg-red-50 border-red-500 text-red-700'
            )}>
              {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
              <span className="font-semibold text-sm">{message.text}</span>
            </div>
          )}

          <div>
            <label className="flex items-center gap-2 text-sm font-bold text-slate-900 mb-4 uppercase tracking-wider">
              <Shield className="w-4 h-4 text-blue-500" />
              Global Policy Mode
            </label>
            <div className="grid grid-cols-3 gap-3">
              {['auto', 'manual', 'learning'].map(m => (
                <button
                  key={m}
                  disabled={changing}
                  onClick={() => changeMode(m)}
                  className={cn(
                    "py-3 px-4 rounded-xl font-semibold transition-all border-2 flex flex-col items-center gap-1",
                    policyMode === m 
                      ? 'bg-blue-50 border-blue-500 text-blue-700 shadow-sm ring-1 ring-blue-500/20' 
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50',
                    "disabled:opacity-60 disabled:cursor-not-allowed"
                  )}
                >
                  <span className="capitalize">{m}</span>
                  {m === 'learning' && <span className="text-[10px] bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded font-bold uppercase">AI</span>}
                </button>
              ))}
            </div>
            <p className="mt-3 text-xs text-slate-500 flex items-center gap-2 px-1">
              <Info className="w-3.5 h-3.5" />
              {policyMode === 'auto' && "Standard balanced allocation algorithm."}
              {policyMode === 'manual' && "Strict enforcement of user-defined rules."}
              {policyMode === 'learning' && "ML-driven allocation adapts dynamically to traffic patterns."}
            </p>
          </div>

          <div className="border-t border-slate-100 pt-8">
            <h3 className="text-lg font-bold font-display text-slate-900 mb-6 flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-500" />
              Device Override
            </h3>
            
            <form onSubmit={applyOverride} className="space-y-6">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">MAC Address</label>
                <input
                  type="text"
                  value={form.macAddress}
                  onChange={e => setForm({ ...form, macAddress: e.target.value })}
                  placeholder="00:11:22:33:44:55"
                  className={cn(
                    "w-full px-4 py-3 rounded-xl border text-sm font-mono transition-all outline-none",
                    errors.macAddress 
                      ? 'border-red-300 bg-red-50 focus:border-red-500 focus:ring-4 focus:ring-red-100' 
                      : 'border-slate-200 focus:border-blue-500 focus:ring-4 focus:ring-blue-100'
                  )}
                />
                {errors.macAddress && <p className="text-red-600 text-xs mt-1 font-medium">{errors.macAddress}</p>}
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">Bandwidth (kbps)</label>
                  <input
                    type="number"
                    min="100"
                    value={form.bandwidthKbps}
                    onChange={e => setForm({ ...form, bandwidthKbps: e.target.value })}
                    className={cn(
                      "w-full px-4 py-3 rounded-xl border text-sm transition-all outline-none font-mono",
                      errors.bandwidthKbps 
                        ? 'border-red-300 bg-red-50 focus:border-red-500 focus:ring-4 focus:ring-red-100' 
                        : 'border-slate-200 focus:border-blue-500 focus:ring-4 focus:ring-blue-100'
                    )}
                  />
                  {errors.bandwidthKbps && <p className="text-red-600 text-xs mt-1 font-medium">{errors.bandwidthKbps}</p>}
                </div>

                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">Priority Level</label>
                  <select
                    value={form.priority}
                    onChange={e => setForm({ ...form, priority: e.target.value })}
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-4 focus:ring-blue-100 outline-none text-sm appearance-none bg-white"
                  >
                    <option value="1">High (Critical)</option>
                    <option value="2">Medium (Standard)</option>
                    <option value="3">Low (Background)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Duration</label>
                <select
                  value={form.durationSec}
                  onChange={e => setForm({ ...form, durationSec: e.target.value })}
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-4 focus:ring-blue-100 outline-none text-sm appearance-none bg-white"
                >
                  <option value="300">5 minutes</option>
                  <option value="1800">30 minutes</option>
                  <option value="3600">1 hour</option>
                  <option value="86400">1 day</option>
                  <option value="">Permanent</option>
                </select>
              </div>

              <div className="flex gap-4 pt-4">
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 py-3 bg-linear-to-r from-blue-600 to-indigo-600 text-white font-bold rounded-xl shadow-lg hover:shadow-xl hover:-translate-y-px disabled:opacity-60 disabled:hover:translate-y-0 disabled:shadow-none transition-all active:scale-[0.98]"
                >
                  {submitting ? 'Applying...' : 'Apply Override'}
                </button>
                <button
                  type="button"
                  onClick={clearOverride}
                  disabled={submitting || !form.macAddress}
                  className="flex-1 py-3 bg-white border border-red-200 text-red-600 hover:bg-red-50 font-bold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Clear Rule
                </button>
              </div>
            </form>
          </div>

          <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-5">
            <p className="text-sm text-blue-800 flex items-start gap-3 leading-relaxed">
              <Info className="w-5 h-5 shrink-0 mt-0.5 text-blue-600" />
              <span>
                <strong>System Note:</strong> Overrides take precedence over global policy settings. Learning mode will incorporate these manual overrides into future predictions.
              </span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PolicyControls;
