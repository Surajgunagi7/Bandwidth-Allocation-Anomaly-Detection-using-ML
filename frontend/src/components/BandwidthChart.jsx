import React, { useEffect, useState } from 'react';
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
  ResponsiveContainer
} from 'recharts';
import { BarChart3, TrendingUp } from 'lucide-react';
import api from '@/services/api';
import { cn } from '@/lib/utils';

const BandwidthChart = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('total');

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const res = await api.getHistory(20);
      const history = res?.history || [];

      const transformed = history.map(entry => {
        const date = new Date(entry.timestamp);
        const timeLabel = date.toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        });

        let high = 0;
        let medium = 0;
        let low = 0;

        (entry.final || []).forEach(item => {
          const mbps = (item.predicted_bandwidth_kbps || 0) / 1000;
          if (item.priority === 1) high += mbps;
          else if (item.priority === 2) medium += mbps;
          else if (item.priority === 3) low += mbps;
        });

        return {
          time: timeLabel,
          total: high + medium + low,
          high,
          medium,
          low
        };
      });

      setData(transformed);
    } catch (err) {
      console.error('Failed to fetch bandwidth history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    const id = setInterval(fetchHistory, 5000);
    return () => clearInterval(id);
  }, []);

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-lg">
        <p className="font-semibold text-slate-900 mb-2">{label}</p>
        {payload.map((p, i) => (
          <div key={i} className="flex justify-between gap-3 text-sm">
            <span className="text-slate-600">{p.name}</span>
            <span className="font-mono font-bold">
              {p.value.toFixed(2)} Mbps
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-8 shadow-sm relative">
      {loading && (
        <div className="absolute inset-0 bg-white/50 backdrop-blur-sm flex items-center justify-center z-10">
          <div className="flex flex-col items-center gap-2">
            <div className="w-10 h-10 border-4 border-slate-200 border-t-blue-500 rounded-full animate-spin" />
            <span className="text-sm text-slate-600">Loading bandwidth data…</span>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600">
            <BarChart3 className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Bandwidth Usage</h2>
            <p className="text-sm text-slate-500">Live ML allocation output</p>
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
            onClick={() => setView('priority')}
            className={cn(
              'px-4 py-1.5 text-sm font-medium rounded-md',
              view === 'priority'
                ? 'bg-white shadow text-slate-900'
                : 'text-slate-600'
            )}
          >
            By Priority
          </button>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-slate-500">
          <TrendingUp className="w-10 h-10 mb-2" />
          <p>No bandwidth history yet</p>
        </div>
      ) : (
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            {view === 'total' ? (
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="time" />
                <YAxis label={{ value: 'Mbps', angle: -90, position: 'insideLeft' }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="total"
                  name="Total Bandwidth"
                  stroke="#3b82f6"
                  strokeWidth={3}
                  dot={false}
                />
              </LineChart>
            ) : (
              <AreaChart data={data}>
                <defs>
                  <linearGradient id="high" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="medium" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="low" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>

                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="time" />
                <YAxis label={{ value: 'Mbps', angle: -90, position: 'insideLeft' }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend />

                <Area type="monotone" dataKey="high" name="High Priority" stroke="#ef4444" fill="url(#high)" />
                <Area type="monotone" dataKey="medium" name="Medium Priority" stroke="#f59e0b" fill="url(#medium)" />
                <Area type="monotone" dataKey="low" name="Low Priority" stroke="#10b981" fill="url(#low)" />
              </AreaChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default BandwidthChart;
