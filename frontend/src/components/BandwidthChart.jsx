import React, { useState, useEffect } from 'react';
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
import { TrendingUp, BarChart3 } from 'lucide-react';
import api from '../services/api';
import { cn } from '@/lib/utils';

const BandwidthChart = () => {
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('total');

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const data = await api.getHistory(20);
      const history = data.history || [];
      
      const transformed = history.map((entry) => {
        const timestamp = new Date(entry.timestamp).toLocaleTimeString([], { 
          hour: '2-digit', 
          minute: '2-digit' 
        });
        const predictions = entry.predictions || [];
        
        const byPriority = predictions.reduce((acc, pred) => {
          const priority = pred.priority || 2;
          acc[priority] = (acc[priority] || 0) + (pred.predicted_bandwidth_kbps || 0);
          return acc;
        }, {});
        
        return {
          time: timestamp,
          total: predictions.reduce((sum, p) => sum + (p.predicted_bandwidth_kbps || 0), 0) / 1000,
          high: (byPriority[1] || 0) / 1000,
          medium: (byPriority[2] || 0) / 1000,
          low: (byPriority[3] || 0) / 1000,
        };
      });
      
      setChartData(transformed);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    const interval = setInterval(fetchHistory, 5000);
    return () => clearInterval(interval);
  }, []);

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white/95 backdrop-blur-sm p-4 rounded-lg shadow-xl border border-slate-200">
          <p className="font-semibold font-display text-slate-900 mb-2">{label}</p>
          {payload.map((entry, index) => (
            <div key={index} className="flex items-center gap-2 text-sm mb-1">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-slate-600">{entry.name}:</span>
              <span className="font-mono font-bold text-slate-900">
                {entry.value.toFixed(2)} Mbps
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-xl p-8 shadow-sm border border-slate-200 hover:shadow-md transition-shadow relative">
      {loading && (
        <div className="absolute inset-0 bg-white/40 backdrop-blur-sm rounded-xl flex items-center justify-center z-10 pointer-events-none">
          <div className="flex flex-col items-center gap-3">
            <div className="relative w-12 h-12">
              <div className="absolute inset-0 border-4 border-slate-100 rounded-full"></div>
              <div className="absolute inset-0 border-4 border-transparent border-t-blue-500 rounded-full animate-spin"></div>
            </div>
            <p className="text-slate-600 font-medium text-sm">Loading chart...</p>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-linear-to-br from-blue-500 to-indigo-600 shadow-md">
            <BarChart3 className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold font-display text-slate-900">Bandwidth Usage</h2>
            <p className="text-sm text-slate-500 mt-1">Real-time traffic analysis</p>
          </div>
        </div>
        
        <div className="flex bg-slate-100 p-1 rounded-lg self-start sm:self-auto">
          <button
            onClick={() => setViewMode('total')}
            className={cn(
              "px-4 py-1.5 rounded-md text-sm font-medium transition-all",
              viewMode === 'total'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            )}
          >
            Total
          </button>
          <button
            onClick={() => setViewMode('by-priority')}
            className={cn(
              "px-4 py-1.5 rounded-md text-sm font-medium transition-all",
              viewMode === 'by-priority'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            )}
          >
            By Priority
          </button>
        </div>
      </div>

      {chartData.length === 0 ? (
        <div className="h-72 flex items-center justify-center">
          <div className="text-center">
            <TrendingUp className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 font-medium">No data available yet</p>
            <p className="text-sm text-slate-400 mt-1">Data will appear as traffic is processed</p>
          </div>
        </div>
      ) : (
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            {viewMode === 'total' ? (
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 12, fill: '#64748b' }}
                  stroke="transparent"
                  tickLine={false}
                  dy={10}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: '#64748b' }}
                  stroke="transparent"
                  tickLine={false}
                  label={{ 
                    value: 'Mbps', 
                    angle: -90, 
                    position: 'insideLeft', 
                    fill: '#94a3b8',
                    fontSize: 12
                  }}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#cbd5e1', strokeWidth: 1 }} />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                <Line
                  type="monotone"
                  dataKey="total"
                  stroke="#3b82f6"
                  strokeWidth={3}
                  dot={false}
                  activeDot={{ r: 6, strokeWidth: 0 }}
                  name="Total Bandwidth"
                  animationDuration={1000}
                />
              </LineChart>
            ) : (
              <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <defs>
                  <linearGradient id="colorHigh" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorMedium" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorLow" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 12, fill: '#64748b' }}
                  stroke="transparent"
                  tickLine={false}
                  dy={10}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: '#64748b' }}
                  stroke="transparent"
                  tickLine={false}
                  label={{ 
                    value: 'Mbps', 
                    angle: -90, 
                    position: 'insideLeft', 
                    fill: '#94a3b8',
                    fontSize: 12
                  }}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#cbd5e1', strokeWidth: 1 }} />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                <Area
                  type="monotone"
                  dataKey="high"
                  stackId="1"
                  stroke="#10b981"
                  fill="url(#colorHigh)"
                  name="High Priority"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="medium"
                  stackId="1"
                  stroke="#f59e0b"
                  fill="url(#colorMedium)"
                  name="Medium Priority"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="low"
                  stackId="1"
                  stroke="#ef4444"
                  fill="url(#colorLow)"
                  name="Low Priority"
                  strokeWidth={2}
                />
              </AreaChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default BandwidthChart;
