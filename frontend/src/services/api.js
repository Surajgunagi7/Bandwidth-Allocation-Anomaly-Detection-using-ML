import axios from "axios";

/**
 * Axios instance
 * Base URL is empty so Vite proxy is used
 */
const apiClient = axios.create({
  baseURL: "",
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * Response interceptor (optional but useful)
 */
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error("API error:", error?.response || error);
    throw error;
  }
);

/**
 * =========================
 * SYSTEM / HEALTH
 * =========================
 */
export const getHealth = () => apiClient.get("/health");

export const getStats = () => apiClient.get("/stats");

export const resetSystem = () =>
  apiClient.post("/api/reset");

/**
 * =========================
 * DEVICES
 * =========================
 */
export const getDevices = () =>
  apiClient.get("/api/devices");

/**
 * =========================
 * ANOMALIES
 * =========================
 */
export const getAnomalies = () =>
  apiClient.get("/api/anomalies");

/**
 * =========================
 * HISTORY
 * =========================
 */
export const getHistory = (limit = 10) =>
  apiClient.get(`/api/history?limit=${limit}`);

/**
 * =========================
 * POLICY
 * =========================
 */
export const setPolicyMode = (mode) =>
  apiClient.post("/api/policy/mode", { mode });

export const setDeviceOverride = ({
  mac_address,
  bandwidth_kbps,
  priority = 2,
  duration_sec = null,
}) =>
  apiClient.post("/api/policy/override", {
    mac_address,
    bandwidth_kbps,
    priority,
    duration_sec,
  });

export const clearDeviceOverride = (macAddress) =>
  apiClient.delete(`/api/policy/override/${macAddress}`);

/**
 * =========================
 * BANDWIDTH CONFIG
 * =========================
 */
export const getBandwidthConfig = () =>
  apiClient.get("/api/bandwidth/config");

export const setBandwidthConfig = (bandwidth_mbps) =>
  apiClient.post("/api/bandwidth/config", {
    bandwidth_mbps,
  });

/**
 * =========================
 * TC STATUS
 * =========================
 */
export const getTcStatus = () =>
  apiClient.get("/api/tc/status");

/**
 * =========================
 * PCAP UPLOAD (OPTIONAL / ADMIN)
 * =========================
 * This should NOT be called from normal UI flows.
 */
export const uploadPcap = (file) => {
  const formData = new FormData();
  formData.append("capture", file);

  return apiClient.post("/traffic", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
};


const api = {
  client: apiClient,
  getHealth,
  getStats,
  resetSystem,
  getDevices,
  getAnomalies,
  getHistory,
  setPolicyMode,
  setDeviceOverride,
  clearDeviceOverride,
  getBandwidthConfig,
  setBandwidthConfig,
  getTcStatus,
  uploadPcap,
};

export default api;


