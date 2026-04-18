import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
const API_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 180000);

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    // Keep browser timeout above backend/Ollama latency for local models.
    timeout: Number.isFinite(API_TIMEOUT_MS) && API_TIMEOUT_MS > 0 ? API_TIMEOUT_MS : 180000,
    headers: {
        "Content-Type": "application/json",
    },
});

export const setAuthToken = (token) => {
    if (token) {
        apiClient.defaults.headers.common.Authorization = `Bearer ${token}`;
    }
};

export const clearAuthToken = () => {
    delete apiClient.defaults.headers.common.Authorization;
};
