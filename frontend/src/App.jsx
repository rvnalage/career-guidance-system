import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";

import ChatPage from "./pages/Chat";
import DashboardPage from "./pages/Dashboard";
import HomePage from "./pages/Home";
import { apiClient, clearAuthToken, setAuthToken } from "./services/api";
import { loginUser, registerUser } from "./services/auth";

const TOKEN_KEY = "career_guidance_token";

const ProtectedRoute = ({ isAuthenticated, children }) => {
    if (!isAuthenticated) {
        return <Navigate to="/" replace />;
    }
    return children;
};

function App() {
    const [token, setToken] = useState(localStorage.getItem(TOKEN_KEY) || "");
    const [currentUser, setCurrentUser] = useState(null);
    const [statusMessage, setStatusMessage] = useState("");

    useEffect(() => {
        if (token) {
            setAuthToken(token);
            localStorage.setItem(TOKEN_KEY, token);
        } else {
            clearAuthToken();
            localStorage.removeItem(TOKEN_KEY);
            setCurrentUser(null);
        }
    }, [token]);

    useEffect(() => {
        const loadCurrentUser = async () => {
            if (!token) {
                return;
            }
            try {
                const response = await apiClient.get("/users/me");
                setCurrentUser(response.data);
            } catch (err) {
                if (err.response?.status === 401) {
                    setToken("");
                    setStatusMessage("Session expired. Please login again.");
                }
            }
        };

        loadCurrentUser();
    }, [token]);

    const authActions = useMemo(
        () => ({
            onRegister: async (payload) => {
                const data = await registerUser(payload);
                setStatusMessage(data.message || "Registration successful");
            },
            onLogin: async (payload) => {
                const data = await loginUser(payload);
                setToken(data.access_token);
                setStatusMessage("Login successful");
            },
            onLogout: () => {
                setToken("");
                setCurrentUser(null);
                setStatusMessage("Logged out");
            },
        }),
        [],
    );

    return (
        <BrowserRouter>
            <div className="app-shell">
                <header className="topbar">
                    <div>
                        <p className="eyebrow">MTech Final Year Project</p>
                        <h1>Career Guidance System</h1>
                    </div>
                    <nav className="nav-links">
                        <NavLink to="/">Home</NavLink>
                        <NavLink to="/chat">Chat</NavLink>
                        <NavLink to="/dashboard">Dashboard</NavLink>
                    </nav>
                    <button className="button ghost" onClick={authActions.onLogout} disabled={!token}>
                        Logout
                    </button>
                </header>

                {statusMessage ? <p className="status-banner">{statusMessage}</p> : null}

                <main className="content-wrap">
                    <Routes>
                        <Route
                            path="/"
                            element={
                                <HomePage
                                    isAuthenticated={Boolean(token)}
                                    onRegister={authActions.onRegister}
                                    onLogin={authActions.onLogin}
                                />
                            }
                        />
                        <Route
                            path="/chat"
                            element={<ChatPage isAuthenticated={Boolean(token)} currentUser={currentUser} />}
                        />
                        <Route
                            path="/dashboard"
                            element={
                                <ProtectedRoute isAuthenticated={Boolean(token)}>
                                    <DashboardPage currentUser={currentUser} />
                                </ProtectedRoute>
                            }
                        />
                    </Routes>
                </main>
            </div>
        </BrowserRouter>
    );
}

export default App;
