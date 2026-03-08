import { useEffect, useState } from "react";

import { apiClient } from "../services/api";

function ChatPage({ isAuthenticated, currentUser }) {
    const [message, setMessage] = useState("");
    const [chat, setChat] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        const loadHistory = async () => {
            if (!isAuthenticated) {
                return;
            }
            try {
                const response = await apiClient.get("/history/me");
                const history = (response.data.messages || []).map((entry) => ({
                    role: entry.role,
                    text: entry.text,
                }));
                setChat(history);
            } catch (err) {
                setError(err.response?.data?.detail || "Could not load previous chat history");
            }
        };

        loadHistory();
    }, [isAuthenticated]);

    const sendMessage = async (event) => {
        event.preventDefault();
        if (!message.trim() || loading) {
            return;
        }

        setError("");

        const userText = message.trim();
        setChat((prev) => [...prev, { role: "user", text: userText }]);
        setMessage("");
        setLoading(true);

        try {
            const response = isAuthenticated
                ? await apiClient.post("/chat/message/me", {
                    message: userText,
                    context: {},
                })
                : await apiClient.post("/chat/message", {
                    user_id: currentUser?.user_id || "frontend-session-user",
                    message: userText,
                    context: {},
                });

            setChat((prev) => [
                ...prev,
                {
                    role: "assistant",
                    text: response.data.reply,
                    nextStep: response.data.suggested_next_step,
                    citations: response.data.rag_citations || [],
                },
            ]);
        } catch (err) {
            if (err.response?.status === 401) {
                setError("Session expired. Please login again.");
            }
            setChat((prev) => [
                ...prev,
                {
                    role: "assistant",
                    text: err.response?.data?.detail || "Unable to reach chat service",
                },
            ]);
        } finally {
            setLoading(false);
        }
    };

    const clearHistory = async () => {
        setError("");
        if (!isAuthenticated) {
            setChat([]);
            return;
        }

        try {
            await apiClient.delete("/history/me");
            setChat([]);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not clear chat history");
        }
    };

    return (
        <section className="card chat-layout">
            <h2>Career Guidance Chat</h2>
            {error ? <p className="error-text">{error}</p> : null}
            <div className="chat-feed">
                {chat.length === 0 ? <p className="muted-text">Ask about careers, skills, or interviews.</p> : null}
                {chat.map((entry, index) => (
                    <article key={`${entry.role}-${index}`} className={`chat-bubble ${entry.role}`}>
                        <p>{entry.text}</p>
                        {entry.nextStep ? <small>Next: {entry.nextStep}</small> : null}
                        {entry.citations?.length ? (
                            <div className="citation-block">
                                <small>Sources:</small>
                                {entry.citations.map((citation) => (
                                    <p key={`${citation.source}-${citation.title}`} className="citation-item">
                                        [{citation.source_type}] {citation.title}
                                    </p>
                                ))}
                            </div>
                        ) : null}
                    </article>
                ))}
            </div>

            <form className="chat-input-row" onSubmit={sendMessage}>
                <input
                    value={message}
                    placeholder="Type your career question"
                    onChange={(event) => setMessage(event.target.value)}
                />
                <button className="button" type="submit" disabled={loading}>
                    {loading ? "Sending..." : "Send"}
                </button>
            </form>

            <button className="button ghost" type="button" onClick={clearHistory}>
                {isAuthenticated ? "Clear Saved History" : "Clear Local Chat"}
            </button>
        </section>
    );
}

export default ChatPage;
