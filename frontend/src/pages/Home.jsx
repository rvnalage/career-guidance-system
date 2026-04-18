import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const initialRegister = {
    email: "",
    password: "",
    interests: ["AI"],
    target_roles: ["Machine Learning Engineer"],
};

const initialLogin = { email: "", password: "" };

function HomePage({ isAuthenticated, onRegister, onLogin }) {
    const navigate = useNavigate();
    const [registerForm, setRegisterForm] = useState(initialRegister);
    const [loginForm, setLoginForm] = useState(initialLogin);
    const [error, setError] = useState("");

    const submitRegister = async (event) => {
        event.preventDefault();
        setError("");
        try {
            const usernameFromEmail = registerForm.email.split("@")[0]?.trim() || "User";
            await onRegister({
                ...registerForm,
                full_name: usernameFromEmail,
            });
            setRegisterForm(initialRegister);
        } catch (err) {
            setError(err.response?.data?.detail || "Registration failed");
        }
    };

    const submitLogin = async (event) => {
        event.preventDefault();
        setError("");
        try {
            await onLogin(loginForm);
            setLoginForm(initialLogin);
            navigate("/dashboard");
        } catch (err) {
            setError(err.response?.data?.detail || "Login failed");
        }
    };

    return (
        <section className="hero-grid">
            <article className="card panel-intro">
                <p className="eyebrow">Agentic AI + React + FastAPI + ML + NLP + LLM + RAG + XAI</p>
                <h2 className="page-heading-row"><span className="page-heading-symbol" aria-hidden="true">🧭</span>Personalized Career Navigation</h2>
                <p>
                    Explore role fit, skill gaps, and interview preparation with an agentic pipeline tailored for
                    your background.
                </p>
                <p className="muted-text home-links-title">Quick access</p>
                <div className="home-links-grid">
                    <Link className="button quick-access-link qa-chat" to="/chat">Chat Guidance</Link>
                    <Link className="button quick-access-link qa-reco" to="/recommendations">Recommendations</Link>
                    <Link className="button quick-access-link qa-jobs" to="/jobs">Jobs</Link>
                    <Link className="button quick-access-link qa-profile" to="/profile">Profile</Link>
                    <Link className="button quick-access-link qa-settings" to="/settings">Settings</Link>
                    <Link className="button quick-access-link qa-dashboard" to="/dashboard">Dashboard</Link>
                </div>
            </article>

            <article className="card form-card">
                <h3>Create Account</h3>
                <form className="auth-form auth-register-form" onSubmit={submitRegister}>
                    <div className="auth-row">
                        <label className="field-label" htmlFor="register-username">Username</label>
                        <input
                            id="register-username"
                            type="email"
                            placeholder="Enter username email"
                            value={registerForm.email}
                            onChange={(event) => setRegisterForm((prev) => ({ ...prev, email: event.target.value }))}
                            required
                        />
                    </div>
                    <div className="auth-row">
                        <label className="field-label" htmlFor="register-password">Password</label>
                        <input
                            id="register-password"
                            type="password"
                            placeholder="Enter password"
                            value={registerForm.password}
                            onChange={(event) => setRegisterForm((prev) => ({ ...prev, password: event.target.value }))}
                            required
                        />
                    </div>
                    <button type="submit" className="button auth-submit-btn">
                        Register
                    </button>
                </form>

                <h3>Login</h3>
                <form className="auth-form auth-login-form" onSubmit={submitLogin}>
                    <div className="auth-row">
                        <label className="field-label" htmlFor="login-username">Username</label>
                        <input
                            id="login-username"
                            type="email"
                            placeholder="Enter username email"
                            value={loginForm.email}
                            onChange={(event) => setLoginForm((prev) => ({ ...prev, email: event.target.value }))}
                            required
                        />
                    </div>
                    <div className="auth-row">
                        <label className="field-label" htmlFor="login-password">Password</label>
                        <input
                            id="login-password"
                            type="password"
                            placeholder="Enter password"
                            value={loginForm.password}
                            onChange={(event) => setLoginForm((prev) => ({ ...prev, password: event.target.value }))}
                            required
                        />
                    </div>
                    <button type="submit" className="button secondary auth-submit-btn">
                        Login
                    </button>
                </form>

                {error ? <p className="error-text">{error}</p> : null}
            </article>
        </section>
    );
}

export default HomePage;
