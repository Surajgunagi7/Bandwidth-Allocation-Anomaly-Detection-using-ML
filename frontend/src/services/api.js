// API Service for WiFi Bandwidth Controller
const API_BASE_URL = 'http://10.0.2.15:5000';

class ApiService {
  constructor(baseURL = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  // Helper method for fetch requests
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      throw error;
    }
  }

  // System endpoints
  async getHealth() {
    return this.request('/health');
  }

  async getStats() {
    return this.request('/stats');
  }

  async resetSystem() {
    return this.request('/api/reset', { method: 'POST' });
  }

  // Device endpoints
  async getDevices() {
    return this.request('/api/devices');
  }

  // Anomaly endpoints
  async getAnomalies() {
    return this.request('/api/anomalies');
  }

  // History endpoints
  async getHistory(limit = 20) {
    return this.request(`/api/history?limit=${limit}`);
  }

  // Policy endpoints
  async setPolicyMode(mode) {
    return this.request('/api/policy/mode', {
      method: 'POST',
      body: JSON.stringify({ mode }),
    });
  }

  async setDeviceOverride(macAddress, bandwidthKbps, priority, durationSec = null) {
    return this.request('/api/policy/override', {
      method: 'POST',
      body: JSON.stringify({
        mac_address: macAddress,
        bandwidth_kbps: bandwidthKbps,
        priority,
        duration_sec: durationSec,
      }),
    });
  }

  async clearDeviceOverride(macAddress) {
    return this.request(`/api/policy/override/${macAddress}`, {
      method: 'DELETE',
    });
  }

  // Bandwidth configuration
  async getBandwidthConfig() {
    return this.request('/api/bandwidth/config');
  }

  async setBandwidthConfig(bandwidthMbps) {
    return this.request('/api/bandwidth/config', {
      method: 'POST',
      body: JSON.stringify({ bandwidth_mbps: bandwidthMbps }),
    });
  }

  // Traffic Control status
  async getTcStatus() {
    return this.request('/api/tc/status');
  }

  // Upload PCAP file
  async uploadPcap(file) {
    const formData = new FormData();
    formData.append('capture', file);

    const response = await fetch(`${this.baseURL}/traffic`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }

    return await response.json();
  }

  // Upload raw PCAP data
  async uploadRawPcap(data, filename = 'capture.pcap') {
    const response = await fetch(`${this.baseURL}/traffic`, {
      method: 'POST',
      headers: {
        'X-Filename': filename,
      },
      body: data,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }

    return await response.json();
  }
}

// Create singleton instance
const api = new ApiService();

export default api;