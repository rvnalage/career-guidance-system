import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    // Chat requests can take longer when RAG + local LLM are enabled.
    timeout: 60000,
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
