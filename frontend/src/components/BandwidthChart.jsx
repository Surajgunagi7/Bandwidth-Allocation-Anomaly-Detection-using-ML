import React, { useEffect, useMemo, useState } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { BarChart3, RefreshCw, TrendingUp } from 'lucide-react';
import api from '@/services/api';
import { cn } from '@/lib/utils';

const POLL_INTERVAL_MS = 5000;
const HISTORY_LIMIT = 30;

const BandwidthChart = () => {
  const [data, setData] = useState([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [view, setView] = useState('total'); // 'total' | 'devices'

  const fetchHistory = async (isInitial = false) => {
    try {
      if (isInitial) setInitialLoading(true);
      else setRefreshing(true);

      const res = await api.getHistory(HISTORY_LIMIT);
      const history = res?.history || [];

      // Oldest → newest
      const transformed = history
        .slice()
        .reverse()
        .map((entry) => {
          const date = new Date(entry.timestamp);
          const time = date.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          });

          let total = 0;
          const devices = {};

          (entry.final || []).forEach((item) => {
            const mac = item.mac_address || 'unknown';
            const mbps = (item.predicted_bandwidth_kbps || 0) / 1000;
            devices[mac] = mbps;
            total += mbps;
          });

          return { time, total, ...devices };
        });

      setData(transformed);
    } catch (err) {
      console.error('Failed to fetch bandwidth history:', err);
    } finally {
      setInitialLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHistory(true);
    const id = setInterval(() => fetchHistory(false), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  const deviceKeys = useMemo(() => {
    if (!data.length) return [];
    return Object.keys(data[0]).filter(
      (k) => k !== 'time' && k !== 'total'
    );
  }, [data]);

  const colors = [
    '#3b82f6',
    '#8b5cf6',
    '#10b981',
    '#f59e0b',
    '#ef4444',
    '#14b8a6',
    '#6366f1',
  ];

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-8 shadow-sm relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600">
            <BarChart3 className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900">
              Bandwidth Allocation
            </h2>
            <p className="text-sm text-slate-500">
             Dynamic bandwidth redistribution by ML (per device)
            </p>
          </div>
        </div>

        <div className="flex bg-slate-100 p-1 rounded-lg">
          <button
            onClick={() => setView('total')}
            className={cn(
              'px-4 py-1.5 text-sm font-medium rounded-md',
              view === 'total'
                ? 'bg-white shadow text-slate-900'
                : 'text-slate-600'
            )}
          >
            Total
          </button>
          <button
            onClick={() => setView('devices')}
            className={cn(
              'px-4 py-1.5 text-sm font-medium rounded-md',
              view === 'devices'
                ? 'bg-white shadow text-slate-900'
                : 'text-slate-600'
            )}
          >
            Per Device
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="h-80">
        {initialLoading ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-400">
            <TrendingUp className="w-12 h-12 mb-3" />
            <p className="font-medium">Loading bandwidth history…</p>
          </div>
        ) : data.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-400">
            <TrendingUp className="w-12 h-12 mb-3" />
            <p className="font-medium">No history available yet</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            {view === 'total' ? (
              <AreaChart data={data}>
                <defs>
                  <linearGradient id="totalGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>

                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="time" />
                <YAxis
                  label={{
                    value: 'Mbps',
                    angle: -90,
                    position: 'insideLeft',
                  }}
                />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="total"
                  stroke="#3b82f6"
                  strokeWidth={3}
                  fill="url(#totalGrad)"
                  name="Total Bandwidth"
                />
              </AreaChart>
            ) : (
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="time" />
                <YAxis
                  label={{
                    value: 'Mbps',
                    angle: -90,
                    position: 'insideLeft',
                  }}
                />
                <Tooltip />
                <Legend />
                {deviceKeys.map((key, i) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    name={`Device ${key.slice(-5)}`}
                    stroke={colors[i % colors.length]}
                    strokeWidth={2}
                    dot={false}
                  />
                ))}
              </LineChart>
            )}
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default BandwidthChart;
