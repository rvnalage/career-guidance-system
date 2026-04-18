import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";

import ChatPage from "./pages/Chat";
import DashboardPage from "./pages/Dashboard";
import HomePage from "./pages/Home";
import JobsPage from "./pages/Jobs";
import ProfilePage from "./pages/Profile";
import RecommendationsPage from "./pages/Recommendations";
import SettingsPage from "./pages/Settings";
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
    const isLoggedIn = Boolean(token && token.trim());

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
                }
            }
        };

        loadCurrentUser();
    }, [token]);

    const authActions = useMemo(
        () => ({
            onRegister: async (payload) => {
                await registerUser(payload);
            },
            onLogin: async (payload) => {
                const data = await loginUser(payload);
                setToken(data.access_token);
            },
            onLogout: () => {
                setToken("");
                setCurrentUser(null);
            },
        }),
        [],
    );

    return (
        <BrowserRouter>
            <div className="app-shell">
                <header className="topbar">
                    <div className="topbar-main">
                        <h1 className="project-title">
                            <span className="project-title-icon" aria-hidden="true">
                                <svg viewBox="0 0 24 24" className="project-title-svg" focusable="false">
                                    <path d="M8 7V6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v1h2a2 2 0 0 1 2 2v2H4V9a2 2 0 0 1 2-2h2zm2 0h4V6h-4v1z" />
                                    <path d="M4 13h7v1.2a1 1 0 0 0 1 1h0a1 1 0 0 0 1-1V13h7v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-5z" />
                                    <path d="M8 18.5l2.2-2.1 1.7 1.5 3.3-3.2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                            </span>
                            <span className="project-title-text">Agentic AI Based Personalized Career Guidance System</span>
                        </h1>
                        {isLoggedIn ? (
                            <button className="button ghost" onClick={authActions.onLogout}>
                                Logout
                            </button>
                        ) : null}
                    </div>
                    <nav className="nav-links">
                        <NavLink to="/">Home</NavLink>
                        <NavLink to="/chat">Chat</NavLink>
                        <NavLink to="/recommendations">Recommend</NavLink>
                        <NavLink to="/jobs">Jobs</NavLink>
                        <NavLink to="/profile">Profile</NavLink>
                        <NavLink to="/settings">Settings</NavLink>
                        <NavLink to="/dashboard">Dashboard</NavLink>
                    </nav>
                </header>

                <main className="content-wrap">
                    <Routes>
                        <Route
                            path="/"
                            element={
                                <HomePage
                                    isAuthenticated={isLoggedIn}
                                    onRegister={authActions.onRegister}
                                    onLogin={authActions.onLogin}
                                />
                            }
                        />
                        <Route
                            path="/chat"
                            element={<ChatPage isAuthenticated={isLoggedIn} currentUser={currentUser} />}
                        />
                        <Route
                            path="/dashboard"
                            element={
                                <ProtectedRoute isAuthenticated={isLoggedIn}>
                                    <DashboardPage currentUser={currentUser} />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/profile"
                            element={
                                <ProtectedRoute isAuthenticated={isLoggedIn}>
                                    <ProfilePage isAuthenticated={isLoggedIn} currentUser={currentUser} />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/recommendations"
                            element={
                                <ProtectedRoute isAuthenticated={isLoggedIn}>
                                    <RecommendationsPage isAuthenticated={isLoggedIn} currentUser={currentUser} />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/jobs"
                            element={
                                <ProtectedRoute isAuthenticated={isLoggedIn}>
                                    <JobsPage />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/settings"
                            element={
                                <ProtectedRoute isAuthenticated={isLoggedIn}>
                                    <SettingsPage />
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
