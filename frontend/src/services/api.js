import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem("token", token);
  } else {
    localStorage.removeItem("token");
  }
}

export function removeToken() {
  localStorage.removeItem("token");
}

export async function health() {
  const { data } = await api.get("/health");
  return data;
}

export async function fetchAdminUsers() {
  const { data } = await api.get("/admin/users");
  return data;
}

export async function fetchAdminDocuments() {
  const { data } = await api.get("/admin/documents");
  return data;
}

export async function fetchAdminStats() {
  const { data } = await api.get("/admin/stats");
  return data;
}

// Admin User CRUD APIs
export async function createAdminUser(userData) {
  const { data } = await api.post("/admin/users", userData);
  return data;
}

export async function updateAdminUser(userId, userData) {
  const { data } = await api.put(`/admin/users/${userId}`, userData);
  return data;
}

export async function deleteAdminUser(userId) {
  await api.delete(`/admin/users/${userId}`);
}

// Auth APIs
export async function register(email, password, fullName) {
  const { data } = await api.post("/auth/register", {
    email,
    password,
    full_name: fullName,
  });
  return data;
}

export async function login(email, password) {
  const { data } = await api.post("/auth/login-json", {
    email,
    password,
  });
  return data;
}

export async function getMe() {
  const { data } = await api.get("/auth/me");
  return data;
}

// Document APIs
export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function listDocuments() {
  const { data } = await api.get("/documents/");
  return data;
}

export async function getDocument(documentId) {
  const { data } = await api.get(`/documents/${documentId}`);
  return data;
}

export async function deleteDocument(documentId) {
  await api.delete(`/documents/${documentId}`);
}

// Query APIs
export async function askQuestion(
  question,
  documentIds, // ← THAY ĐỔI: Array thay vì single ID
  conversationId = null,
  signal = null
) {
  const config = {};
  if (signal) {
    config.signal = signal;
  }

  const { data } = await api.post(
    "/query/ask",
    {
      question,
      document_ids: documentIds, // ← MỚI: Array
      conversation_id: conversationId,
    },
    config
  );

  if (!data) {
    throw new Error("No data received from server");
  }

  return data;
}

export async function getQueryHistory(documentId = null, limit = 20) {
  const params = { limit };
  if (documentId) params.document_id = documentId;
  const { data } = await api.get("/query/history", { params });
  return data;
}

// History APIs
export async function getHistory(documentId = null, limit = 20) {
  const params = { limit };
  if (documentId) params.document_id = documentId;
  const { data } = await api.get("/history/", { params });
  return data;
}

export async function deleteHistory(historyId) {
  await api.delete(`/history/${historyId}`);
}

export async function deleteConversation(conversationId) {
  await api.delete(`/history/conversation/${conversationId}`);
}

export async function deleteHistoryByDocument(documentId) {
  await api.delete(`/history/document/${documentId}`);
}

export async function deleteAllHistory() {
  await api.delete(`/history/all`);
}
