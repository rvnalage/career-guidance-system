import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    // Keep the browser-side timeout above the backend/Ollama window used for local models.
    timeout: 180000,
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
