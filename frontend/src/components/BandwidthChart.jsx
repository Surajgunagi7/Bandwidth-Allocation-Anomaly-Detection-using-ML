import React, { useState, useEffect } from 'react';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp } from 'lucide-react';
import apiService from '../services/api';

const BandwidthChart = () => {
  const [chartData, setChartData] = useState([]);
  const [viewMode, setViewMode] = useState('total'); // 'total' or 'by-priority'

  const fetchHistory = async () => {
    try {
      const data = await apiService.getHistory(20);
      const history = data.history || [];
      
      // Transform history into chart data
      const transformed = history.map((entry) => {
        const timestamp = new Date(entry.timestamp).toLocaleTimeString();
        const predictions = entry.predictions || [];
        
        // Calculate total bandwidth by priority
        const byPriority = predictions.reduce((acc, pred) => {
          const priority = pred.priority || 2;
          acc[priority] = (acc[priority] || 0) + (pred.predicted_bandwidth_kbps || 0);
          return acc;
        }, {});
        
        return {
          time: timestamp,
          total: predictions.reduce((sum, p) => sum + (p.predicted_bandwidth_kbps || 0), 0) / 1000, // Convert to Mbps
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
        <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-medium text-gray-900 mb-2">{label}</p>
          {payload.map((entry, index) => (
            <div key={index} className="flex items-center text-sm">
              <div
                className="w-3 h-3 rounded-full mr-2"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-gray-600 mr-2">{entry.name}:</span>
              <span className="font-medium text-gray-900">
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
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <TrendingUp className="w-5 h-5 text-blue-600 mr-2" />
          <h2 className="text-xl font-semibold text-gray-900">Bandwidth Usage</h2>
        </div>
        
        <div className="flex space-x-2">
          <button
            onClick={() => setViewMode('total')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              viewMode === 'total'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Total
          </button>
          <button
            onClick={() => setViewMode('by-priority')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              viewMode === 'by-priority'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            By Priority
          </button>
        </div>
      </div>

      {chartData.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-gray-500">
          <div className="text-center">
            <TrendingUp className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p>No data available yet</p>
            <p className="text-sm text-gray-400 mt-2">Data will appear as traffic is processed</p>
          </div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          {viewMode === 'total' ? (
            <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 12 }}
                stroke="#6b7280"
              />
              <YAxis
                tick={{ fontSize: 12 }}
                stroke="#6b7280"
                label={{ value: 'Bandwidth (Mbps)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Line
                type="monotone"
                dataKey="total"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                name="Total Bandwidth"
              />
            </LineChart>
          ) : (
            <AreaChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 12 }}
                stroke="#6b7280"
              />
              <YAxis
                tick={{ fontSize: 12 }}
                stroke="#6b7280"
                label={{ value: 'Bandwidth (Mbps)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Area
                type="monotone"
                dataKey="high"
                stackId="1"
                stroke="#10b981"
                fill="#10b981"
                fillOpacity={0.6}
                name="High Priority"
              />
              <Area
                type="monotone"
                dataKey="medium"
                stackId="1"
                stroke="#f59e0b"
                fill="#f59e0b"
                fillOpacity={0.6}
                name="Medium Priority"
              />
              <Area
                type="monotone"
                dataKey="low"
                stackId="1"
                stroke="#ef4444"
                fill="#ef4444"
                fillOpacity={0.6}
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