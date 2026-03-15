import { useEffect, useState } from "react";

import { apiClient } from "../services/api";

const initialForm = {
    interests: "AI, Data Science",
    skills: "Python, Machine Learning, SQL",
    education_level: "master",
};

function DashboardPage() {
    const [summary, setSummary] = useState(null);
    const [report, setReport] = useState(null);
    const [recommendations, setRecommendations] = useState([]);
    const [recommendationHistory, setRecommendationHistory] = useState([]);
    const [chatHistory, setChatHistory] = useState([]);
    const [form, setForm] = useState(initialForm);
    const [error, setError] = useState("");
    const [loadingHistory, setLoadingHistory] = useState(false);
    const [explanations, setExplanations] = useState([]);
    const [jobs, setJobs] = useState([]);
    const [jobQuery, setJobQuery] = useState("data");
    const [psychometric, setPsychometric] = useState({
        investigative: 4,
        realistic: 3,
        artistic: 3,
        social: 4,
        enterprising: 3,
        conventional: 3,
    });
    const [psychometricResult, setPsychometricResult] = useState(null);
    const [ragStatus, setRagStatus] = useState(null);
    const [ragQuery, setRagQuery] = useState("career roadmap");
    const [ragResults, setRagResults] = useState([]);
    const [ragBusy, setRagBusy] = useState(false);
    const [llmStatus, setLlmStatus] = useState(null);
    const [xaiStatus, setXaiStatus] = useState(null);
    const [ownerType, setOwnerType] = useState("self");
    const [uploadFiles, setUploadFiles] = useState([]);
    const [uploadBusy, setUploadBusy] = useState(false);
    const [uploadMessage, setUploadMessage] = useState("");
    const [pendingRecommendationClearTarget, setPendingRecommendationClearTarget] = useState(null);

    const loadSummary = async () => {
        try {
            const response = await apiClient.get("/dashboard/summary/me");
            setSummary(response.data);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load dashboard summary");
        }
    };

    const loadDashboardReport = async () => {
        try {
            const response = await apiClient.get("/dashboard/report/me");
            setReport(response.data);
        } catch {
            setReport(null);
        }
    };

    const loadHistoryPanels = async () => {
        setLoadingHistory(true);
        try {
            const [chatResponse, recommendationResponse] = await Promise.all([
                apiClient.get("/history/me"),
                apiClient.get("/recommendations/history/me"),
            ]);
            setChatHistory(chatResponse.data.messages || []);
            setRecommendationHistory(recommendationResponse.data.history || []);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load activity history");
        } finally {
            setLoadingHistory(false);
        }
    };

    useEffect(() => {
        loadSummary();
        loadDashboardReport();
        loadHistoryPanels();
        loadMarketJobs("data");
        loadPsychometricProfile();
        loadRagStatus();
        loadSystemStatus();
    }, []);

    const loadSystemStatus = async () => {
        try {
            const [llmResponse, xaiResponse] = await Promise.all([
                apiClient.get("/llm/status"),
                apiClient.get("/recommendations/xai/status"),
            ]);
            setLlmStatus(llmResponse.data);
            setXaiStatus(xaiResponse.data);
        } catch {
            // The dashboard remains usable even if optional diagnostics cannot be loaded.
        }
    };

    const loadRagStatus = async () => {
        try {
            const response = await apiClient.get("/rag/status");
            setRagStatus(response.data);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load RAG status");
        }
    };

    const ingestDefaultRag = async () => {
        setRagBusy(true);
        try {
            await apiClient.post("/rag/ingest/default");
            await loadRagStatus();
        } catch (err) {
            setError(err.response?.data?.detail || "Could not ingest default RAG documents");
        } finally {
            setRagBusy(false);
        }
    };

    const searchRag = async (event) => {
        event.preventDefault();
        if (!ragQuery.trim()) {
            return;
        }
        setRagBusy(true);
        try {
            const response = await apiClient.get(`/rag/search?query=${encodeURIComponent(ragQuery)}`);
            setRagResults(response.data.results || []);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not search RAG references");
        } finally {
            setRagBusy(false);
        }
    };

    const loadPsychometricProfile = async () => {
        try {
            const response = await apiClient.get("/psychometric/profile/me");
            const data = response.data;
            if (data && Object.keys(data.normalized_scores || {}).length > 0) {
                setPsychometricResult(data);
            }
        } catch (err) {
            if (err.response?.status !== 401) {
                setError(err.response?.data?.detail || "Could not load psychometric profile");
            }
        }
    };

    const loadMarketJobs = async (query) => {
        try {
            const response = await apiClient.get(`/market/jobs?search=${encodeURIComponent(query)}&limit=6`);
            setJobs(response.data.results || []);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load job market data");
        }
    };

    const loadExplanationPanel = async () => {
        try {
            const response = await apiClient.post("/recommendations/explain/me", {
                interests: form.interests.split(",").map((item) => item.trim()).filter(Boolean),
                skills: form.skills.split(",").map((item) => item.trim()).filter(Boolean),
                education_level: form.education_level,
            });
            setExplanations(response.data.explanations || []);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not generate recommendation explanations");
        }
    };

    const generateRecommendations = async (event) => {
        event.preventDefault();
        setError("");
        try {
            const response = await apiClient.post("/recommendations/generate", {
                interests: form.interests.split(",").map((item) => item.trim()).filter(Boolean),
                skills: form.skills.split(",").map((item) => item.trim()).filter(Boolean),
                education_level: form.education_level,
            });
            setRecommendations(response.data.recommendations || []);
            await loadExplanationPanel();
            await loadSummary();
            await loadDashboardReport();
            await loadHistoryPanels();
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to generate recommendations");
        }
    };

    const submitRecommendationFeedback = async (role, helpful) => {
        try {
            await apiClient.post("/recommendations/feedback/me", {
                role,
                helpful,
                rating: helpful ? 5 : 2,
                feedback_tags: ["skills", "interests"],
            });
        } catch (err) {
            setError(err.response?.data?.detail || "Could not submit feedback");
        }
    };

    const scorePsychometric = async () => {
        try {
            const response = await apiClient.post("/psychometric/score/me", {
                dimensions: psychometric,
            });
            setPsychometricResult(response.data);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not score psychometric profile");
        }
    };

    const uploadProfileFiles = async () => {
        if (uploadFiles.length === 0) {
            return;
        }

        setUploadBusy(true);
        setUploadMessage("");
        try {
            const formData = new FormData();
            formData.append("owner_type", ownerType);
            uploadFiles.forEach((file) => formData.append("files", file));

            const response = await apiClient.post("/profile-intake/upload", formData, {
                headers: {
                    "Content-Type": "multipart/form-data",
                },
            });

            const extracted = response.data?.extracted_profile || {};
            if ((extracted.skills || []).length > 0) {
                setForm((prev) => ({ ...prev, skills: extracted.skills.join(", ") }));
            }
            if ((extracted.interests || []).length > 0) {
                setForm((prev) => ({ ...prev, interests: extracted.interests.join(", ") }));
            }
            if (extracted.education_level) {
                setForm((prev) => ({ ...prev, education_level: extracted.education_level }));
            }
            if (extracted.psychometric_dimensions) {
                setPsychometric((prev) => ({ ...prev, ...extracted.psychometric_dimensions }));
            }

            setUploadMessage(response.data?.message || "Upload parsed.");
            await loadSummary();
            await loadDashboardReport();
        } catch (err) {
            setUploadMessage(err.response?.data?.detail || "Could not parse uploaded files");
        } finally {
            setUploadBusy(false);
        }
    };

    const recentMessages = chatHistory.slice(-6);
    const latestRecommendationSnapshot = recommendationHistory[0]?.recommendations || [];
    const effectiveRecommendations = recommendations.length > 0
        ? recommendations
        : report?.latest_recommendations?.length > 0
            ? report.latest_recommendations
            : latestRecommendationSnapshot;
    const effectiveRecentMessages = report?.recent_chat_messages?.length > 0
        ? report.recent_chat_messages.slice(-6)
        : recentMessages;
    const recommendationRuns = recommendationHistory.length;
    const conversationTurns = chatHistory.length;
    const nextAction = summary?.next_action || "Generate recommendations to build your next plan";
    const topRolesText = summary?.top_roles?.length ? summary.top_roles.join(", ") : "No roles shortlisted yet";
    const profileSignals = [
        `${form.skills.split(",").map((item) => item.trim()).filter(Boolean).length} skill signals`,
        `${form.interests.split(",").map((item) => item.trim()).filter(Boolean).length} interest signals`,
        `${form.education_level} education context`,
    ].join(" • ");

    const exportDashboardReport = async () => {
        let reportPayload;
        try {
            const response = await apiClient.get("/dashboard/report/me");
            reportPayload = response.data;
        } catch {
            // Fallback keeps export usable if report endpoint is temporarily unavailable.
            reportPayload = {
                generated_at: new Date().toISOString(),
                summary: summary || {},
                latest_recommendations: recommendations.length > 0 ? recommendations : latestRecommendationSnapshot,
                recommendation_history: recommendationHistory,
                recent_chat_messages: recentMessages,
            };
        }

        reportPayload.input_snapshot = {
            interests: form.interests,
            skills: form.skills,
            education_level: form.education_level,
        };

        const blob = new Blob([JSON.stringify(reportPayload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `agentic-career-intelligence-report-${new Date().toISOString().slice(0, 10)}.json`;
        anchor.click();
        URL.revokeObjectURL(url);
    };

    const clearRecommendationLocalView = async () => {
        setRecommendations([]);
        setExplanations([]);
    };

    const clearRecommendationHistory = async () => {
        setError("");
        try {
            await apiClient.delete("/recommendations/history/me");
            setRecommendations([]);
            setExplanations([]);
            await loadSummary();
            await loadDashboardReport();
            await loadHistoryPanels();
        } catch (err) {
            setError(err.response?.data?.detail || "Could not clear recommendation history");
        }
    };

    const confirmRecommendationClear = async () => {
        if (pendingRecommendationClearTarget === "local") {
            await clearRecommendationLocalView();
        }
        if (pendingRecommendationClearTarget === "backend") {
            await clearRecommendationHistory();
        }
        setPendingRecommendationClearTarget(null);
    };

    return (
        <section className="dashboard-stack">
            <article className="card dashboard-hero">
                <div>
                    <p className="eyebrow">Context Aware Dashboard</p>
                    <h2>Decision workspace built around your current profile context</h2>
                    <p className="muted-text dashboard-hero-copy">
                        Keep the recommendation workflow, chat evidence, psychometric signals, and retrieval context in one place.
                    </p>
                    <div className="dashboard-pill-row">
                        <span className="dashboard-pill">{profileSignals}</span>
                        <span className="dashboard-pill">{conversationTurns} chat turns</span>
                        <span className="dashboard-pill">{recommendationRuns} recommendation runs</span>
                    </div>
                </div>
                <div className="dashboard-hero-metrics">
                    <div className="metric-item metric-highlight">
                        <span>Profile Completion</span>
                        <strong>{summary ? `${summary.profile_completion}%` : "--"}</strong>
                    </div>
                    <div className="metric-item">
                        <span>Current Focus</span>
                        <strong>{topRolesText}</strong>
                    </div>
                    <div className="metric-item">
                        <span>Next Action</span>
                        <strong>{nextAction}</strong>
                    </div>
                </div>
            </article>

            <section className="dashboard-layout">
                <div className="dashboard-main-column">
                    <article className="card dashboard-primary-panel">
                        <div className="panel-header-actions">
                            <div>
                                <p className="eyebrow">Recommendation Workspace</p>
                                <h2>Generate and compare career directions</h2>
                            </div>
                            <button className="button secondary" type="button" onClick={exportDashboardReport}>
                                Export Report JSON
                            </button>
                        </div>
                        <p className="muted-text section-copy">
                            Update your active skills, interests, and education context, then run the recommendation engine and explanation panel together.
                        </p>
                        <form onSubmit={generateRecommendations}>
                            <input
                                value={form.interests}
                                onChange={(event) => setForm((prev) => ({ ...prev, interests: event.target.value }))}
                                placeholder="Interests (comma separated)"
                            />
                            <input
                                value={form.skills}
                                onChange={(event) => setForm((prev) => ({ ...prev, skills: event.target.value }))}
                                placeholder="Skills (comma separated)"
                            />
                            <select
                                value={form.education_level}
                                onChange={(event) => setForm((prev) => ({ ...prev, education_level: event.target.value }))}
                            >
                                <option value="high_school">High School</option>
                                <option value="diploma">Diploma</option>
                                <option value="bachelor">Bachelor</option>
                                <option value="master">Master</option>
                                <option value="phd">PhD</option>
                            </select>
                            <button className="button" type="submit">
                                Run Recommendation Engine
                            </button>
                            <button className="button ghost" type="button" onClick={() => setPendingRecommendationClearTarget("local")}>
                                Clear Recommendation View
                            </button>
                            <button className="button ghost" type="button" onClick={() => setPendingRecommendationClearTarget("backend")}>
                                Clear Saved Recommendation History
                            </button>
                        </form>

                        {pendingRecommendationClearTarget ? (
                            <div className="confirm-panel">
                                <p>
                                    {pendingRecommendationClearTarget === "backend"
                                        ? "Confirm clear of saved recommendation history from backend?"
                                        : "Confirm clear of recommendation results visible in this dashboard?"}
                                </p>
                                <div className="confirm-panel-actions">
                                    <button className="button" type="button" onClick={confirmRecommendationClear}>
                                        Confirm Clear
                                    </button>
                                    <button className="button secondary" type="button" onClick={() => setPendingRecommendationClearTarget(null)}>
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        ) : null}

                        {effectiveRecommendations.length > 0 ? (
                            <div className="recommendation-list">
                                {effectiveRecommendations.map((item) => (
                                    <article key={item.role} className="recommendation-item">
                                        <h4>{item.role}</h4>
                                        <p>{item.reason}</p>
                                        <small>Confidence: {(item.confidence * 100).toFixed(1)}%</small>
                                        <div className="feedback-row">
                                            <button
                                                className="button secondary"
                                                type="button"
                                                onClick={() => submitRecommendationFeedback(item.role, true)}
                                            >
                                                Helpful
                                            </button>
                                            <button
                                                className="button ghost"
                                                type="button"
                                                onClick={() => submitRecommendationFeedback(item.role, false)}
                                            >
                                                Not Helpful
                                            </button>
                                        </div>
                                    </article>
                                ))}
                            </div>
                        ) : null}

                        {error ? <p className="error-text">{error}</p> : null}
                    </article>

                    <article className="card dashboard-primary-panel">
                        <div className="panel-header-actions">
                            <div>
                                <p className="eyebrow">Why These Roles</p>
                                <h2>Explanation panel</h2>
                            </div>
                            <div className="status-chip-row">
                                {xaiStatus ? <span className="status-chip">XAI: {xaiStatus.active_mode}</span> : null}
                                {llmStatus ? <span className="status-chip">LLM: {llmStatus.enabled ? "enabled" : "disabled"}</span> : null}
                            </div>
                        </div>
                        {explanations.length === 0 ? (
                            <p className="muted-text">Generate recommendations to view feature contribution explanations.</p>
                        ) : (
                            <div className="explanation-grid">
                                {explanations.map((item) => (
                                    <article key={item.role} className="history-item">
                                        <h3>{item.role}</h3>
                                        <small>{item.label}</small>
                                        {item.contributions.map((contribution) => (
                                            <div key={`${item.role}-${contribution.feature}`} className="contribution-row">
                                                <span>{contribution.feature}</span>
                                                <strong>{(contribution.value * 100).toFixed(1)}%</strong>
                                            </div>
                                        ))}
                                    </article>
                                ))}
                            </div>
                        )}
                    </article>

                    <article className="card dashboard-primary-panel">
                        <div className="panel-header-actions">
                            <div>
                                <p className="eyebrow">Evidence And Continuity</p>
                                <h2>Recent activity and last recommendation context</h2>
                            </div>
                        </div>
                        {loadingHistory ? <p className="muted-text">Loading activity timeline...</p> : null}

                        <div className="history-grid">
                            <section>
                                <h3>Recent Chat</h3>
                                {effectiveRecentMessages.length === 0 ? (
                                    <p className="muted-text">No chat history yet. Start a conversation in Chat.</p>
                                ) : (
                                    <div className="history-list">
                                        {effectiveRecentMessages.map((item, index) => (
                                            <article key={`${item.role}-${index}`} className="history-item">
                                                <small>{item.role}</small>
                                                <p>{item.text || item.content}</p>
                                            </article>
                                        ))}
                                    </div>
                                )}
                            </section>

                            <section>
                                <h3>Last Recommendation Run</h3>
                                {effectiveRecommendations.length === 0 ? (
                                    <p className="muted-text">Run recommendation engine to capture snapshots.</p>
                                ) : (
                                    <div className="history-list">
                                        {effectiveRecommendations.map((item) => (
                                            <article key={item.role} className="history-item">
                                                <small>{item.role}</small>
                                                <p>{item.reason}</p>
                                            </article>
                                        ))}
                                    </div>
                                )}
                            </section>
                        </div>
                    </article>
                </div>

                <aside className="dashboard-side-column">
                    <article className="card side-panel">
                        <p className="eyebrow">System Context</p>
                        <h2>Runtime signals</h2>
                        <div className="metric-grid compact-grid">
                            <div className="metric-item">
                                <span>LLM</span>
                                <strong>{llmStatus ? (llmStatus.enabled ? "Enabled" : "Disabled") : "--"}</strong>
                            </div>
                            <div className="metric-item">
                                <span>XAI Mode</span>
                                <strong>{xaiStatus?.active_mode || "--"}</strong>
                            </div>
                            <div className="metric-item">
                                <span>RAG Chunks</span>
                                <strong>{ragStatus?.total_chunks ?? "--"}</strong>
                            </div>
                            <div className="metric-item">
                                <span>Active Model</span>
                                <strong>{llmStatus?.active_model || "--"}</strong>
                            </div>
                        </div>
                    </article>

                    <article className="card side-panel">
                        <div className="panel-header-actions">
                            <div>
                                <p className="eyebrow">Knowledge Context</p>
                                <h2>RAG search</h2>
                            </div>
                            <button className="button secondary" type="button" onClick={ingestDefaultRag} disabled={ragBusy}>
                                {ragBusy ? "Processing..." : "Ingest Docs"}
                            </button>
                        </div>
                        <form className="inline-form" onSubmit={searchRag}>
                            <input value={ragQuery} onChange={(event) => setRagQuery(event.target.value)} placeholder="Search retrieval context" />
                            <button className="button" type="submit" disabled={ragBusy}>
                                Search
                            </button>
                        </form>

                        <div className="history-list compact-history-list">
                            {ragResults.length === 0 ? (
                                <p className="muted-text">Search retrieved knowledge to inspect grounding context.</p>
                            ) : (
                                ragResults.map((citation, index) => (
                                    <article key={`${citation.source}-${index}`} className="history-item">
                                        <h4>{citation.title}</h4>
                                        <p>{citation.snippet}</p>
                                        <small>
                                            {citation.source_type}: {citation.source}
                                        </small>
                                    </article>
                                ))
                            )}
                        </div>
                    </article>

                    <article className="card side-panel">
                        <p className="eyebrow">Market Context</p>
                        <h2>Live role demand</h2>
                        <form
                            className="inline-form"
                            onSubmit={(event) => {
                                event.preventDefault();
                                loadMarketJobs(jobQuery);
                            }}
                        >
                            <input value={jobQuery} onChange={(event) => setJobQuery(event.target.value)} placeholder="Search jobs" />
                            <button className="button" type="submit">
                                Search
                            </button>
                        </form>
                        <div className="history-list compact-history-list">
                            {jobs.map((job) => (
                                <article key={`${job.company}-${job.job_title}`} className="history-item">
                                    <h4>{job.job_title}</h4>
                                    <p>
                                        {job.company} - {job.location}
                                    </p>
                                    <small>{job.category}</small>
                                </article>
                            ))}
                        </div>
                    </article>

                    <article className="card side-panel">
                        <p className="eyebrow">Profile Context</p>
                        <h2>Psychometric scoring</h2>
                        <div className="chat-context-card" style={{ marginBottom: "0.75rem" }}>
                            <label>
                                Owner
                                <select value={ownerType} onChange={(event) => setOwnerType(event.target.value)}>
                                    <option value="self">For myself</option>
                                    <option value="on_behalf">On behalf of someone</option>
                                </select>
                            </label>
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
                                    onClick={uploadProfileFiles}
                                    disabled={uploadBusy || uploadFiles.length === 0}
                                >
                                    {uploadBusy ? "Parsing..." : "Parse Profile Files"}
                                </button>
                            </div>
                            {uploadMessage ? <p className="muted-text">{uploadMessage}</p> : null}
                        </div>
                        <div className="psychometric-grid">
                            {Object.keys(psychometric).map((trait) => (
                                <label key={trait} className="slider-row">
                                    <span>{trait}</span>
                                    <input
                                        type="range"
                                        min="1"
                                        max="5"
                                        value={psychometric[trait]}
                                        onChange={(event) =>
                                            setPsychometric((prev) => ({
                                                ...prev,
                                                [trait]: Number(event.target.value),
                                            }))
                                        }
                                    />
                                    <strong>{psychometric[trait]}</strong>
                                </label>
                            ))}
                        </div>
                        <button className="button" type="button" onClick={scorePsychometric}>
                            Score Psychometric Profile
                        </button>
                        {psychometricResult ? (
                            <div className="history-list">
                                <article className="history-item">
                                    <h4>Top Traits</h4>
                                    <p>{psychometricResult.top_traits.join(", ")}</p>
                                </article>
                                <article className="history-item">
                                    <h4>Recommended Domains</h4>
                                    <p>{psychometricResult.recommended_domains.join(", ")}</p>
                                </article>
                            </div>
                        ) : null}
                    </article>
                </aside>
            </section>
        </section>
    );
}

export default DashboardPage;
