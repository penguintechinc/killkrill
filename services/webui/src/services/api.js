import axios from "axios";

const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8080";

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Handle response errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

// Auth API
export const authAPI = {
  login: (username, password) =>
    api.post("/api/v1/auth/login", { username, password }),
  logout: () => api.post("/api/v1/auth/logout"),
  refresh: () => api.post("/api/v1/auth/refresh"),
};

// Dashboard API
export const dashboardAPI = {
  getOverview: () => api.get("/api/v1/dashboard/overview"),
  getServices: () => api.get("/api/v1/dashboard/services"),
  getMetrics: () => api.get("/api/v1/dashboard/metrics"),
  getActivity: (params) => api.get("/api/v1/dashboard/activity", { params }),
};

// Sensors API
export const sensorsAPI = {
  // Agents
  getAgents: (params) => api.get("/api/v1/sensors/agents", { params }),
  getAgent: (id) => api.get(`/api/v1/sensors/agents/${id}`),
  createAgent: (data) => api.post("/api/v1/sensors/agents", data),
  updateAgent: (id, data) => api.put(`/api/v1/sensors/agents/${id}`, data),
  deleteAgent: (id) => api.delete(`/api/v1/sensors/agents/${id}`),

  // Checks
  getChecks: (params) => api.get("/api/v1/sensors/checks", { params }),
  getCheck: (id) => api.get(`/api/v1/sensors/checks/${id}`),
  createCheck: (data) => api.post("/api/v1/sensors/checks", data),
  updateCheck: (id, data) => api.put(`/api/v1/sensors/checks/${id}`, data),
  deleteCheck: (id) => api.delete(`/api/v1/sensors/checks/${id}`),

  // Results
  getResults: (params) => api.get("/api/v1/sensors/results", { params }),
  getResult: (id) => api.get(`/api/v1/sensors/results/${id}`),
};

// Token management
export const tokenManager = {
  getToken: () => localStorage.getItem("token"),
  setToken: (token) => localStorage.setItem("token", token),
  removeToken: () => localStorage.removeItem("token"),
};

export default api;
