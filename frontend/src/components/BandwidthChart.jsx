import React, { useState, useEffect } from 'react';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, BarChart3 } from 'lucide-react';
import apiService from '../services/api';

const BandwidthChart = () => {
  const [chartData, setChartData] = useState([]);
  const [viewMode, setViewMode] = useState('total');

  const fetchHistory = async () => {
    try {
      const data = await apiService.getHistory(20);
      const history = data.history || [];
      
      const transformed = history.map((entry) => {
        const timestamp = new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
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
        <div className="glass-card p-4 border border-purple-500/20">
          <p className="font-semibold text-gray-900 mb-2">{label}</p>
          {payload.map((entry, index) => (
            <div key={index} className="flex items-center text-sm gap-2 mb-1">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-gray-600">{entry.name}:</span>
              <span className="font-semibold text-gray-900">
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
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500">
            <BarChart3 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Bandwidth Usage</h2>
            <p className="text-sm text-gray-600">Real-time traffic analysis</p>
          </div>
        </div>
        
        <div className="flex gap-2">
          <button
            onClick={() => setViewMode('total')}
            className={`btn-pill !py-2 !px-4 !text-xs transition-smooth ${
              viewMode === 'total' ? 'btn-primary' : 'btn-secondary'
            }`}
          >
            Total
          </button>
          <button
            onClick={() => setViewMode('by-priority')}
            className={`btn-pill !py-2 !px-4 !text-xs transition-smooth ${
              viewMode === 'by-priority' ? 'btn-primary' : 'btn-secondary'
            }`}
          >
            By Priority
          </button>
        </div>
      </div>

      {chartData.length === 0 ? (
        <div className="h-64 flex items-center justify-center">
          <div className="text-center">
            <TrendingUp className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600 font-medium">No data available yet</p>
            <p className="text-sm text-gray-500 mt-2">Data will appear as traffic is processed</p>
          </div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          {viewMode === 'total' ? (
            <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <defs>
                <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#667eea" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#667eea" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 12, fill: '#6b7280' }}
                stroke="#d1d5db"
              />
              <YAxis
                tick={{ fontSize: 12, fill: '#6b7280' }}
                stroke="#d1d5db"
                label={{ value: 'Bandwidth (Mbps)', angle: -90, position: 'insideLeft', fill: '#6b7280' }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              <Line
                type="monotone"
                dataKey="total"
                stroke="url(#gradientPurple)"
                strokeWidth={3}
                dot={false}
                name="Total Bandwidth"
                fill="url(#colorTotal)"
              />
            </LineChart>
          ) : (
            <AreaChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <defs>
                <linearGradient id="colorHigh" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.2}/>
                </linearGradient>
                <linearGradient id="colorMedium" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.2}/>
                </linearGradient>
                <linearGradient id="colorLow" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0.2}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 12, fill: '#6b7280' }}
                stroke="#d1d5db"
              />
              <YAxis
                tick={{ fontSize: 12, fill: '#6b7280' }}
                stroke="#d1d5db"
                label={{ value: 'Bandwidth (Mbps)', angle: -90, position: 'insideLeft', fill: '#6b7280' }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              <Area
                type="monotone"
                dataKey="high"
                stackId="1"
                stroke="#10b981"
                fill="url(#colorHigh)"
                name="High Priority"
              />
              <Area
                type="monotone"
                dataKey="medium"
                stackId="1"
                stroke="#f59e0b"
                fill="url(#colorMedium)"
                name="Medium Priority"
              />
              <Area
                type="monotone"
                dataKey="low"
                stackId="1"
                stroke="#ef4444"
                fill="url(#colorLow)"
                name="Low Priority"
              />
            </AreaChart>
          )}
        </ResponsiveContainer>
      )}
    </div>
  );
};

export default BandwidthChart;