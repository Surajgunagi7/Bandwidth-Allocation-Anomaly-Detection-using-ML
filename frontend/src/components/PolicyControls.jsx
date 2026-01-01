import React, { useEffect, useMemo, useState } from 'react';
import {
  Settings2,
  CheckCircle,
  AlertCircle,
  X,
  Info,
  Shield,
} from 'lucide-react';
import api from '@/services/api';
import { cn } from '@/lib/utils';

const POLICY_MODES = ['auto', 'equal', 'manual'];

const emptyForm = {
  mac: '',
  bandwidthKbps: '5000',
  priority: '2',
  durationSec: '3600',
};

const PolicyControls = ({ selectedDevice, onClose }) => {
  const [policyMode, setPolicyMode] = useState(null);
  const [changingMode, setChangingMode] = useState(false);

  const [form, setForm] = useState(emptyForm);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(true);

  const validate = () => {
    const err = {};
    if (!form.mac) err.mac = 'MAC address is required';
    else if (!/^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/.test(form.mac))
      err.mac = 'Invalid MAC format';

    if (Number(form.bandwidthKbps) < 100)
      err.bandwidthKbps = 'Minimum 100 kbps';

    setErrors(err);
    return Object.keys(err).length === 0;
  };

  const showMessage = (m) => {
    setMessage(m);
    setTimeout(() => setMessage(null), 3000);
  };

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        setLoading(true);
        const mode = await api.getPolicyMode();
        if (alive) setPolicyMode(mode || 'auto');
      } catch {
        if (alive) setPolicyMode('auto');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (selectedDevice) {
      setForm({
        mac: selectedDevice.mac || '',
        bandwidthKbps: String(selectedDevice.bandwidth_kbps ?? 5000),
        priority: String(selectedDevice.priority ?? 2),
        durationSec: '3600',
      });
    } else {
      setForm(emptyForm);
    }
    setErrors({});
  }, [selectedDevice]);

  const changePolicyMode = async (mode) => {
    if (mode === policyMode) return;
    setChangingMode(true);
    try {
      await api.setPolicyMode(mode);
      setPolicyMode(mode);
      showMessage({ type: 'success', text: `Global policy set to ${mode}` });
    } catch {
      showMessage({ type: 'error', text: 'Failed to change global policy' });
    } finally {
      setChangingMode(false);
    }
  };

  const applyOverride = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setSubmitting(true);
    try {
      await api.setDeviceOverride({
        mac_address: form.mac,
        bandwidth_kbps: Number(form.bandwidthKbps),
        priority: Number(form.priority),
        duration_sec: form.durationSec ? Number(form.durationSec) : null,
      });
      showMessage({ type: 'success', text: 'Device override applied' });
      setTimeout(onClose, 800);
    } catch {
      showMessage({ type: 'error', text: 'Failed to apply override' });
    } finally {
      setSubmitting(false);
    }
  };

  const clearOverride = async () => {
    if (!form.mac) return;
    setSubmitting(true);
    try {
      await api.clearDeviceOverride(form.mac);
      showMessage({ type: 'success', text: 'Device override cleared' });
      setTimeout(onClose, 800);
    } catch {
      showMessage({ type: 'error', text: 'Failed to clear override' });
    } finally {
      setSubmitting(false);
    }
  };

  const hasDevice = useMemo(() => Boolean(form.mac), [form.mac]);
  const canOverride = policyMode === 'manual';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full border border-slate-200">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b">
          <div className="flex items-center gap-3">
            <Settings2 className="w-6 h-6 text-blue-600" />
            <h2 className="text-xl font-bold">Policy Controls</h2>
          </div>
          <button onClick={onClose} className="p-2 rounded hover:bg-slate-100">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Message */}
          {message && (
            <div
              className={cn(
                'p-3 rounded-lg border-l-4 flex items-center gap-2',
                message.type === 'success'
                  ? 'bg-emerald-50 border-emerald-500 text-emerald-700'
                  : 'bg-red-50 border-red-500 text-red-700'
              )}
            >
              {message.type === 'success' ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                <AlertCircle className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">{message.text}</span>
            </div>
          )}

          {/* Global Policy */}
          <section className="bg-slate-50 rounded-xl p-5 border">
            <label className="block text-sm font-bold mb-3 flex items-center gap-2">
              <Shield className="w-4 h-4 text-blue-500" />
              Global Policy Mode
            </label>

            {loading ? (
              <div className="text-sm text-slate-500">Loading policy…</div>
            ) : (
              <div className="grid grid-cols-3 gap-3">
                {POLICY_MODES.map((mode) => (
                  <button
                    key={mode}
                    disabled={changingMode}
                    onClick={() => changePolicyMode(mode)}
                    className={cn(
                      'py-2 rounded-lg font-semibold border transition',
                      policyMode === mode
                        ? 'bg-blue-50 border-blue-500 text-blue-700'
                        : 'border-slate-200 text-slate-600 hover:bg-slate-100'
                    )}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            )}

            <div className="mt-3 text-xs text-slate-500 flex gap-2">
              <Info className="w-4 h-4 shrink-0" />
              <p>
                Global policy defines how bandwidth is distributed system-wide.
                Device overrides (below) take precedence.
              </p>
            </div>
          </section>

          {/* Device Override */}
          <section className="border rounded-xl p-5">
            <h3 className="font-bold mb-4">Device-Specific Override</h3>

            <form onSubmit={applyOverride} className="space-y-4">
              <div>
                <label className="text-sm font-semibold">MAC Address</label>
                <input
                  value={form.mac}
                  onChange={(e) => setForm({ ...form, mac: e.target.value })}
                  className="w-full px-3 py-2 border rounded font-mono"
                  placeholder="02:00:00:00:00:00"
                />
                {errors.mac && (
                  <p className="text-xs text-red-600">{errors.mac}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-semibold">Bandwidth (kbps)</label>
                  <input
                    type="number"
                    min="100"
                    value={form.bandwidthKbps}
                    onChange={(e) =>
                      setForm({ ...form, bandwidthKbps: e.target.value })
                    }
                    className="w-full px-3 py-2 border rounded font-mono"
                  />
                  {errors.bandwidthKbps && (
                    <p className="text-xs text-red-600">
                      {errors.bandwidthKbps}
                    </p>
                  )}
                </div>

                <div>
                  <label className="text-sm font-semibold">
                    Scheduler Class (TC)
                  </label>
                  <select
                    value={form.priority}
                    onChange={(e) =>
                      setForm({ ...form, priority: e.target.value })
                    }
                    className="w-full px-3 py-2 border rounded"
                  >
                    <option value="1">Class 1</option>
                    <option value="2">Class 2</option>
                    <option value="3">Class 3</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold">Duration</label>
                <select
                  value={form.durationSec}
                  onChange={(e) =>
                    setForm({ ...form, durationSec: e.target.value })
                  }
                  className="w-full px-3 py-2 border rounded"
                >
                  <option value="300">5 minutes</option>
                  <option value="1800">30 minutes</option>
                  <option value="3600">1 hour</option>
                  <option value="86400">1 day</option>
                  <option value="">Permanent</option>
                </select>
              </div>
              {policyMode !== 'manual' && (
                <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 flex gap-2">
                  <Info className="w-4 h-4 shrink-0" />
                  Device overrides are available only in <b>manual</b> policy mode.
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={submitting || !hasDevice || !canOverride}
                  className={cn(
                    'flex-1 py-2 rounded font-bold',
                    canOverride
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-300 text-slate-500 cursor-not-allowed'
                  )}
                >
                  Apply Override
                </button>
                <button
                  type="button"
                  onClick={clearOverride}
                  disabled={!hasDevice || submitting || !canOverride}
                  className={cn(
                    'flex-1 py-2 rounded font-bold border',
                    canOverride
                      ? 'border-red-300 text-red-600'
                      : 'border-slate-300 text-slate-400 cursor-not-allowed'
                  )}
                >
                  Clear Override
                </button>
              </div>
            </form>

            <div className="mt-3 text-xs text-slate-500 flex gap-2">
              <Info className="w-4 h-4 shrink-0" />
              <p>
                Scheduler class controls TC queueing priority. It does not
                guarantee bandwidth.
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default PolicyControls;
