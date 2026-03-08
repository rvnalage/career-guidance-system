import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const initialRegister = {
    full_name: "",
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
            await onRegister(registerForm);
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
                <p className="eyebrow">Agentic AI + NLP + ML</p>
                <h2>Personalized Career Navigation for Students</h2>
                <p>
                    Explore role fit, skill gaps, and interview preparation with an agentic pipeline tailored for
                    your background.
                </p>
                <div className="cta-row">
                    <Link className="button" to="/chat">
                        Start Chat Guidance
                    </Link>
                    {isAuthenticated ? (
                        <Link className="button secondary" to="/dashboard">
                            Open Dashboard
                        </Link>
                    ) : null}
                </div>
                {isAuthenticated ? <p className="status-inline">You are logged in and can access secure endpoints.</p> : null}
            </article>

            <article className="card form-card">
                <h3>Create Account</h3>
                <form onSubmit={submitRegister}>
                    <input
                        placeholder="Full Name"
                        value={registerForm.full_name}
                        onChange={(event) => setRegisterForm((prev) => ({ ...prev, full_name: event.target.value }))}
                        required
                    />
                    <input
                        type="email"
                        placeholder="Email"
                        value={registerForm.email}
                        onChange={(event) => setRegisterForm((prev) => ({ ...prev, email: event.target.value }))}
                        required
                    />
                    <input
                        type="password"
                        placeholder="Password"
                        value={registerForm.password}
                        onChange={(event) => setRegisterForm((prev) => ({ ...prev, password: event.target.value }))}
                        required
                    />
                    <button type="submit" className="button">
                        Register
                    </button>
                </form>

                <h3>Login</h3>
                <form onSubmit={submitLogin}>
                    <input
                        type="email"
                        placeholder="Email"
                        value={loginForm.email}
                        onChange={(event) => setLoginForm((prev) => ({ ...prev, email: event.target.value }))}
                        required
                    />
                    <input
                        type="password"
                        placeholder="Password"
                        value={loginForm.password}
                        onChange={(event) => setLoginForm((prev) => ({ ...prev, password: event.target.value }))}
                        required
                    />
                    <button type="submit" className="button secondary">
                        Login
                    </button>
                </form>

                {error ? <p className="error-text">{error}</p> : null}
            </article>
        </section>
    );
}

export default HomePage;
