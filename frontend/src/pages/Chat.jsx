import { useEffect, useRef, useState } from "react";

import ConfirmModal from "../components/Common/ConfirmModal";
import { apiClient } from "../services/api";

/* ─────────────────────────────────────────────────────────────────
   Inline markdown renderer — no dependencies.
   Handles: **bold**, *italic*, `code`,  bullet/numbered lists, line breaks.
───────────────────────────────────────────────────────────────── */
function formatInline(str) {
    const parts = str.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/);
    return parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**"))
            return <strong key={i}>{part.slice(2, -2)}</strong>;
        if (part.startsWith("*") && part.endsWith("*"))
            return <em key={i}>{part.slice(1, -1)}</em>;
        if (part.startsWith("`") && part.endsWith("`"))
            return <code key={i} className="msg-inline-code">{part.slice(1, -1)}</code>;
        return part;
    });
}

function renderMessage(text) {
    if (!text) return null;
    const lines = text.split("\n");
    const elements = [];
    let ulItems = [];
    let olItems = [];

    const flushUl = () => {
        if (ulItems.length === 0) return;
        elements.push(<ul key={`ul-${elements.length}`} className="msg-list">{ulItems}</ul>);
        ulItems = [];
    };
    const flushOl = () => {
        if (olItems.length === 0) return;
        elements.push(<ol key={`ol-${elements.length}`} className="msg-list msg-list-ol">{olItems}</ol>);
        olItems = [];
    };

    for (const line of lines) {
        const trimmed = line.trimEnd();
        if (/^[-•*]\s/.test(trimmed)) {
            flushOl();
            ulItems.push(<li key={ulItems.length}>{formatInline(trimmed.slice(2).trim())}</li>);
            continue;
        }
        const olMatch = trimmed.match(/^(\d+)[.)]\s+(.+)/);
        if (olMatch) {
            flushUl();
            olItems.push(<li key={olItems.length}>{formatInline(olMatch[2])}</li>);
            continue;
        }
        flushUl();
        flushOl();
        if (trimmed === "") {
            if (elements.length > 0) elements.push(<div key={`sp-${elements.length}`} className="msg-spacer" />);
        } else {
            elements.push(<p key={`p-${elements.length}`} className="msg-para">{formatInline(trimmed)}</p>);
        }
    }
    flushUl();
    flushOl();
    return elements;
}

function TypingIndicator() {
    return (
        <div className="typing-indicator" aria-label="Assistant is typing">
            <span /><span /><span />
        </div>
    );
}

function SourceBadge({ source }) {
    const map = {
        agent_rag_llm: { label: "RAG + LLM", cls: "badge-llm" },
        agent_rag: { label: "RAG", cls: "badge-rag" },
        agent: { label: "Agent", cls: "badge-agent" },
    };
    const info = map[source] || { label: source, cls: "badge-agent" };
    return <span className={`source-badge ${info.cls}`}>{info.label}</span>;
}

function ChatPage({ isAuthenticated, currentUser }) {
    const [message, setMessage] = useState("");
    const [chat, setChat] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [pendingClearTarget, setPendingClearTarget] = useState(null);
    const chatEndRef = useRef(null);
    const sendInFlightRef = useRef(false);

    // Auto-scroll to newest message.
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [chat, loading]);

    const buildChatPayload = (userText) => ({
        message: userText,
        context: {},
    });

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
                    nextStep: entry.suggested_next_step,
                    citations: entry.rag_citations || [],
                    responseSource: entry.response_source,
                    llmUsed: entry.llm_used,
                    responseTimeMs: entry.response_time_ms,
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
        if (!message.trim() || loading || sendInFlightRef.current) {
            return;
        }
        sendInFlightRef.current = true;

        setError("");

        const userText = message.trim();
        setChat((prev) => [...prev, { role: "user", text: userText }]);
        setMessage("");
        setLoading(true);

        try {
            const response = isAuthenticated
                ? await apiClient.post("/chat/message/me", {
                    ...buildChatPayload(userText),
                })
                : await apiClient.post("/chat/message", {
                    user_id: currentUser?.user_id || "frontend-session-user",
                    ...buildChatPayload(userText),
                });

            setChat((prev) => [
                ...prev,
                {
                    role: "assistant",
                    text: response.data.reply,
                    nextStep: response.data.suggested_next_step,
                    citations: response.data.rag_citations || [],
                    responseSource: response.data.response_source,
                    llmUsed: response.data.llm_used,
                    responseTimeMs: response.data.response_time_ms,
                },
            ]);
        } catch (err) {
            if (err.response?.status === 401) {
                setError("Session expired. Please login again.");
            }
            const failureMessage = err.response?.data?.detail
                || (err.code === "ECONNABORTED"
                    ? "Chat request timed out. Backend is reachable but response took too long."
                    : err.message || "Unable to reach chat service");
            setChat((prev) => [
                ...prev,
                {
                    role: "assistant",
                    text: failureMessage,
                },
            ]);
        } finally {
            setLoading(false);
            sendInFlightRef.current = false;
        }
    };

    const clearSavedHistory = async () => {
        setError("");
        try {
            await apiClient.delete("/history/me");
            setChat([]);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not clear chat history");
        }
    };

    const confirmClear = async () => {
        if (pendingClearTarget === "backend") {
            await clearSavedHistory();
        }
        setPendingClearTarget(null);
    };

    return (
        <section className="card chat-layout">
            <div className="chat-header-row">
                <div className="chat-header-title">
                    <span className="chat-header-icon" aria-hidden="true">🎯</span>
                    <div>
                        <h2>AI Career Coach</h2>
                        <p className="chat-header-sub">RAG-grounded guidance with agentic reasoning</p>
                    </div>
                </div>
            </div>

            {error ? <p className="error-text">{error}</p> : null}

            <div className="chat-feed">
                {chat.length === 0 ? (
                    <div className="chat-empty-state">
                        <span className="chat-empty-icon">💬</span>
                        <p>Ask about career paths, skill gaps, interview prep, or learning roadmaps.</p>
                        <div className="chat-suggestion-chips">
                            <button type="button" className="suggestion-chip" onClick={() => setMessage("What career paths suit a Python developer interested in AI?")}>Python + AI career paths</button>
                            <button type="button" className="suggestion-chip" onClick={() => setMessage("How should I prepare for a data science interview?")}>Data science interview tips</button>
                            <button type="button" className="suggestion-chip" onClick={() => setMessage("Create a 6-month learning roadmap for ML engineering")}>ML roadmap</button>
                        </div>
                    </div>
                ) : null}
                {chat.map((entry, index) => (
                    <article key={`${entry.role}-${index}`} className={`chat-bubble ${entry.role}`}>
                        <div className="bubble-avatar" aria-hidden="true">
                            {entry.role === "user" ? "🧑‍💻" : "🤖"}
                        </div>
                        <div className="bubble-body">
                            <div className="bubble-content">
                                {renderMessage(entry.text)}
                            </div>
                            {(entry.responseSource || entry.nextStep || entry.citations?.length) ? (
                                <div className="bubble-meta">
                                    {entry.responseSource ? (
                                        <div className="bubble-meta-row">
                                            <SourceBadge source={entry.responseSource} />
                                            {typeof entry.responseTimeMs === "number" ? (
                                                <span className="meta-timing">⏱ {entry.responseTimeMs} ms</span>
                                            ) : null}
                                        </div>
                                    ) : null}
                                    {entry.nextStep ? (
                                        <div className="next-step-pill">
                                            <span>💡</span> {entry.nextStep}
                                        </div>
                                    ) : null}
                                    {entry.citations?.length ? (
                                        <div className="citation-block">
                                            <p className="citation-heading">📚 Referenced sources</p>
                                            {entry.citations.map((citation, citationIndex) => (
                                                <p key={`${citation.source || "src"}-${citation.title || "title"}-${citationIndex}`} className="citation-item">
                                                    <span className="citation-type">{citation.source_type}</span>
                                                    {citation.title}
                                                </p>
                                            ))}
                                        </div>
                                    ) : null}
                                </div>
                            ) : null}
                        </div>
                    </article>
                ))}
                {loading ? (
                    <article className="chat-bubble assistant">
                        <div className="bubble-avatar" aria-hidden="true">🤖</div>
                        <div className="bubble-body">
                            <TypingIndicator />
                        </div>
                    </article>
                ) : null}
                <div ref={chatEndRef} />
            </div>

            <div className="chat-input-wrapper">
                <form className="chat-input-row" onSubmit={sendMessage}>
                    <div className="chat-textarea-wrap">
                        <textarea
                            className="chat-textarea"
                            value={message}
                            rows={1}
                            placeholder="Ask about careers, skills, interviews… (Enter to send, Alt+Enter for newline)"
                            onChange={(event) => setMessage(event.target.value)}
                            onKeyDown={(event) => {
                                if (event.key !== "Enter") {
                                    return;
                                }

                                if (event.altKey) {
                                    event.preventDefault();
                                    const textarea = event.currentTarget;
                                    const selectionStart = textarea.selectionStart;
                                    const selectionEnd = textarea.selectionEnd;

                                    setMessage((prev) => (
                                        `${prev.slice(0, selectionStart)}\n${prev.slice(selectionEnd)}`
                                    ));

                                    requestAnimationFrame(() => {
                                        const nextCursor = selectionStart + 1;
                                        textarea.selectionStart = nextCursor;
                                        textarea.selectionEnd = nextCursor;
                                    });
                                    return;
                                }

                                if (!event.altKey) {
                                    event.preventDefault();
                                    if (message.trim() && !loading) sendMessage(event);
                                }
                            }}
                        />
                    </div>
                    <div className="chat-input-actions">
                        <button className="button chat-send-btn" type="submit" disabled={loading || !message.trim()}>
                            {loading ? <span className="send-spinner" /> : "↑ Send"}
                        </button>
                        {isAuthenticated ? (
                            <button
                                className="button ghost chat-clear-btn"
                                type="button"
                                onClick={() => setPendingClearTarget("backend")}
                            >
                                Clear Saved History
                            </button>
                        ) : null}
                    </div>
                </form>
                <p className="input-hint">Enter to send · Alt+Enter for new line</p>
                <article className="chat-context-card profile-tip-card">
                    <p className="profile-tip-title">💡 Profile tip</p>
                    <p className="muted-text">Update skills, interests, and psychometrics in the <strong>Profile</strong> tab.</p>
                </article>
            </div>

            <ConfirmModal
                open={Boolean(pendingClearTarget)}
                title="Confirm Clear"
                message="Confirm clear of saved backend chat history?"
                confirmLabel="Confirm Clear"
                onConfirm={confirmClear}
                onCancel={() => setPendingClearTarget(null)}
            />
        </section>
    );
}

export default ChatPage;
