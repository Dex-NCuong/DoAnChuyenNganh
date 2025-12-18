// Helper to clean URL
const cleanUrl = (url) => {
  if (!url) return "http://localhost:8000";
  // Remove trailing slash and whitespaces
  return url.trim().replace(/\/+$/, "");
};

const API_BASE_URL = cleanUrl(import.meta.env.VITE_API_BASE_URL);

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
