import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error.response?.data || error);
  }
);

// ============= API Methods =============

export const apiService = {
  // Health & Stats
  getHealth: () => api.get('/health'),
  
  getStats: () => api.get('/stats'),
  
  // Devices
  getDevices: () => api.get('/api/devices'),
  
  // Anomalies
  getAnomalies: () => api.get('/api/anomalies'),
  
  // History
  getHistory: (limit = 10) => api.get(`/api/history?limit=${limit}`),
  
  // Policy Control
  setPolicyMode: (mode) => api.post('/api/policy/mode', { mode }),
  
  setDeviceOverride: (macAddress, bandwidthKbps, priority, durationSec = null) => 
    api.post('/api/policy/override', {
      mac_address: macAddress,
      bandwidth_kbps: bandwidthKbps,
      priority,
      duration_sec: durationSec,
    }),
  
  clearDeviceOverride: (macAddress) => 
    api.delete(`/api/policy/override/${macAddress}`),
  
  // Traffic Control
  getTCStatus: () => api.get('/api/tc/status'),
  
  // System Control
  resetSystem: () => api.post('/api/reset'),
  
  // Upload PCAP
  uploadPCAP: (file, onProgress) => {
    const formData = new FormData();
    formData.append('capture', file);
    
    return api.post('/traffic', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentCompleted);
        }
      },
    });
  },
};

export default apiService;