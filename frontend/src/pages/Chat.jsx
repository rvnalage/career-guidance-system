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

const DEFAULT_PSYCHOMETRIC = {
    investigative: 3,
    realistic: 3,
    artistic: 3,
    social: 3,
    enterprising: 3,
    conventional: 3,
};

function ChatPage({ isAuthenticated, currentUser }) {
    const [message, setMessage] = useState("");
    const [chat, setChat] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [ownerType, setOwnerType] = useState("self");
    const [skillsInput, setSkillsInput] = useState("");
    const [interestsInput, setInterestsInput] = useState("");
    const [educationLevel, setEducationLevel] = useState("master");
    const [psychometric, setPsychometric] = useState(DEFAULT_PSYCHOMETRIC);
    const [uploadFiles, setUploadFiles] = useState([]);
    const [uploadMessage, setUploadMessage] = useState("");
    const [uploadLoading, setUploadLoading] = useState(false);
    const [pendingClearTarget, setPendingClearTarget] = useState(null);
    const [isProfileSectionCollapsed, setIsProfileSectionCollapsed] = useState(false);
    const chatEndRef = useRef(null);

    // Auto-scroll to newest message.
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [chat, loading]);

    const parseCsv = (value) =>
        value
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean);

    const buildChatPayload = (userText) => ({
        message: userText,
        context: {},
        context_owner_type: ownerType,
        skills: parseCsv(skillsInput),
        interests: parseCsv(interestsInput),
        education_level: educationLevel || null,
        psychometric_dimensions: psychometric,
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
        }
    };

    const clearLocalChat = async () => {
        setChat([]);
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
        if (pendingClearTarget === "local") {
            await clearLocalChat();
        }
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
                        <h2>Career Intelligence Chat</h2>
                        <p className="chat-header-sub">Powered by RAG + Agentic reasoning</p>
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

            <article className="chat-context-card">
                <div className="collapsible-card-header">
                    <button
                        type="button"
                        className="collapsible-trigger"
                        aria-expanded={!isProfileSectionCollapsed}
                        aria-controls="chat-profile-context-content"
                        onClick={() => setIsProfileSectionCollapsed((prev) => !prev)}
                    >
                        <div>
                            <h3>⚙️ Profile Context</h3>
                        </div>
                        <span className="collapse-icon" aria-hidden="true">
                            {isProfileSectionCollapsed ? "Expand" : "Minimize"}
                        </span>
                    </button>
                </div>

                {!isProfileSectionCollapsed ? (
                    <div id="chat-profile-context-content" className="collapsible-content">
                        <div className="chat-context-grid">
                            <label>
                                Owner
                                <select value={ownerType} onChange={(event) => setOwnerType(event.target.value)}>
                                    <option value="self">For myself</option>
                                    <option value="on_behalf">On behalf of someone</option>
                                </select>
                            </label>
                            <label>
                                Education
                                <select value={educationLevel} onChange={(event) => setEducationLevel(event.target.value)}>
                                    <option value="high_school">High School</option>
                                    <option value="diploma">Diploma</option>
                                    <option value="bachelor">Bachelor</option>
                                    <option value="master">Master</option>
                                    <option value="phd">PhD</option>
                                </select>
                            </label>
                        </div>
                        <label>
                            Skills (comma separated)
                            <input
                                value={skillsInput}
                                placeholder="python, sql, statistics"
                                onChange={(event) => setSkillsInput(event.target.value)}
                            />
                        </label>
                        <label>
                            Interests (comma separated)
                            <input
                                value={interestsInput}
                                placeholder="data science, ai, research"
                                onChange={(event) => setInterestsInput(event.target.value)}
                            />
                        </label>

                        <div className="chat-context-psychometric">
                            <p className="muted-text">Psychometric quick inputs (1-5)</p>
                            {Object.entries(psychometric).map(([dimension, value]) => (
                                <label key={dimension} className="chat-dimension-row">
                                    <span>{dimension}</span>
                                    <input
                                        type="range"
                                        min="1"
                                        max="5"
                                        value={value}
                                        onChange={(event) =>
                                            setPsychometric((prev) => ({
                                                ...prev,
                                                [dimension]: Number(event.target.value),
                                            }))
                                        }
                                    />
                                    <strong>{value}</strong>
                                </label>
                            ))}
                        </div>
                    </div>
                ) : null}
            </article>

            {isAuthenticated ? (
                <article className="chat-context-card">
                    <h3>Upload Profile Files</h3>
                    <p className="muted-text">Upload text files for {ownerType === "self" ? "your profile" : "on-behalf context"} parsing.</p>
                    <div className="chat-upload-row">
                        <input
                            type="file"
                            multiple
                            accept=".txt,.md,.csv,.json,.log"
                            onChange={(event) => setUploadFiles(Array.from(event.target.files || []))}
                        />
                        <button
                            className="button secondary"
                            type="button"
                            disabled={uploadLoading || uploadFiles.length === 0}
                            onClick={async () => {
                                setUploadMessage("");
                                if (uploadFiles.length === 0) {
                                    return;
                                }
                                setUploadLoading(true);
                                try {
                                    const formData = new FormData();
                                    formData.append("owner_type", ownerType);
                                    uploadFiles.forEach((file) => formData.append("files", file));
                                    const response = await apiClient.post("/profile-intake/upload", formData, {
                                        headers: {
                                            "Content-Type": "multipart/form-data",
                                        },
                                    });
                                    const parsed = response.data?.extracted_profile || {};
                                    if ((parsed.skills || []).length > 0) {
                                        setSkillsInput(parsed.skills.join(", "));
                                    }
                                    if ((parsed.interests || []).length > 0) {
                                        setInterestsInput(parsed.interests.join(", "));
                                    }
                                    if (parsed.education_level) {
                                        setEducationLevel(parsed.education_level);
                                    }
                                    if (parsed.psychometric_dimensions) {
                                        setPsychometric((prev) => ({
                                            ...prev,
                                            ...parsed.psychometric_dimensions,
                                        }));
                                    }
                                    setUploadMessage(response.data?.message || "Upload parsed.");
                                } catch (err) {
                                    setUploadMessage(err.response?.data?.detail || "Upload failed.");
                                } finally {
                                    setUploadLoading(false);
                                }
                            }}
                        >
                            {uploadLoading ? "Parsing..." : "Parse Files"}
                        </button>
                    </div>
                    {uploadMessage ? <p className="muted-text">{uploadMessage}</p> : null}
                </article>
            ) : null}

            <div className="chat-input-wrapper">
                <form className="chat-input-row" onSubmit={sendMessage}>
                    <div className="chat-textarea-wrap">
                        <textarea
                            className="chat-textarea"
                            value={message}
                            rows={1}
                            placeholder="Ask about careers, skills, interviews… (Enter to send, Shift+Enter for newline)"
                            onChange={(event) => setMessage(event.target.value)}
                            onKeyDown={(event) => {
                                if (event.key === "Enter" && !event.shiftKey) {
                                    event.preventDefault();
                                    if (message.trim() && !loading) sendMessage(event);
                                }
                            }}
                        />
                    </div>
                    <button className="button chat-send-btn" type="submit" disabled={loading || !message.trim()}>
                        {loading ? <span className="send-spinner" /> : "↑ Send"}
                    </button>
                </form>
                <p className="input-hint">Enter to send · Shift+Enter for new line</p>
            </div>

            <div className="clear-action-row">
                <button className="button ghost" type="button" onClick={() => setPendingClearTarget("local")}>
                    🗑 Clear Screen
                </button>
                {isAuthenticated ? (
                    <button className="button ghost" type="button" onClick={() => setPendingClearTarget("backend")}>
                        🗑 Clear Saved History
                    </button>
                ) : null}
            </div>

            <ConfirmModal
                open={Boolean(pendingClearTarget)}
                title="Confirm Clear"
                message={pendingClearTarget === "backend"
                    ? "Confirm clear of saved backend chat history?"
                    : "Confirm clear of chat currently shown on screen?"}
                confirmLabel="Confirm Clear"
                onConfirm={confirmClear}
                onCancel={() => setPendingClearTarget(null)}
            />
        </section>
    );
}

export default ChatPage;
