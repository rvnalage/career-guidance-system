import { Component, StrictMode } from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./styles/globals.css";

class AppErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, message: "" };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, message: error?.message || "Unknown frontend error" };
    }

    componentDidCatch(error) {
        // Keep the full stack in browser console for debugging.
        console.error("Frontend runtime error:", error);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: "1rem", color: "#1f2532", fontFamily: "Space Grotesk, sans-serif" }}>
                    <h2>Frontend failed to render</h2>
                    <p>{this.state.message}</p>
                    <p>Open browser devtools console for full details.</p>
                </div>
            );
        }
        return this.props.children;
    }
}

ReactDOM.createRoot(document.getElementById("root")).render(
    <StrictMode>
        <AppErrorBoundary>
            <App />
        </AppErrorBoundary>
    </StrictMode>,
);
