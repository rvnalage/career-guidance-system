import { useEffect, useState } from "react";

import { apiClient } from "../services/api";

const initialForm = {
    interests: "AI, Data Science",
    skills: "Python, Machine Learning, SQL",
    education_level: "master",
};

function DashboardPage() {
    const [summary, setSummary] = useState(null);
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

    const loadSummary = async () => {
        try {
            const response = await apiClient.get("/dashboard/summary/me");
            setSummary(response.data);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load dashboard summary");
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
        loadHistoryPanels();
        loadMarketJobs("data");
        loadPsychometricProfile();
        loadRagStatus();
    }, []);

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

    const recentMessages = chatHistory.slice(-6);
    const latestRecommendationSnapshot = recommendationHistory[0]?.recommendations || [];

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
        anchor.download = `career-guidance-report-${new Date().toISOString().slice(0, 10)}.json`;
        anchor.click();
        URL.revokeObjectURL(url);
    };

    const clearRecommendationHistory = async () => {
        setError("");
        try {
            await apiClient.delete("/recommendations/history/me");
            setRecommendations([]);
            await loadSummary();
            await loadHistoryPanels();
        } catch (err) {
            setError(err.response?.data?.detail || "Could not clear recommendation history");
        }
    };

    return (
        <section className="dashboard-grid">
            <article className="card">
                <h2>Progress Snapshot</h2>
                {summary ? (
                    <div className="metric-grid">
                        <div className="metric-item">
                            <span>Profile Completion</span>
                            <strong>{summary.profile_completion}%</strong>
                        </div>
                        <div className="metric-item">
                            <span>Top Roles</span>
                            <strong>{summary.top_roles?.join(", ") || "-"}</strong>
                        </div>
                        <div className="metric-item">
                            <span>Next Action</span>
                            <strong>{summary.next_action}</strong>
                        </div>
                    </div>
                ) : (
                    <p className="muted-text">Loading dashboard...</p>
                )}
            </article>

            <article className="card">
                <h2>Generate Recommendations</h2>
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
                    <button className="button ghost" type="button" onClick={clearRecommendationHistory}>
                        Clear Recommendation History
                    </button>
                </form>

                {recommendations.length > 0 ? (
                    <div className="recommendation-list">
                        {recommendations.map((item) => (
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

            <article className="card dashboard-span">
                <div className="panel-header-actions">
                    <h2>Learning Continuity</h2>
                    <button className="button secondary" type="button" onClick={exportDashboardReport}>
                        Export Report JSON
                    </button>
                </div>
                {loadingHistory ? <p className="muted-text">Loading activity timeline...</p> : null}

                <div className="history-grid">
                    <section>
                        <h3>Recent Chat</h3>
                        {recentMessages.length === 0 ? (
                            <p className="muted-text">No chat history yet. Start a conversation in Chat.</p>
                        ) : (
                            <div className="history-list">
                                {recentMessages.map((item, index) => (
                                    <article key={`${item.role}-${index}`} className="history-item">
                                        <small>{item.role}</small>
                                        <p>{item.text}</p>
                                    </article>
                                ))}
                            </div>
                        )}
                    </section>

                    <section>
                        <h3>Last Recommendation Run</h3>
                        {latestRecommendationSnapshot.length === 0 ? (
                            <p className="muted-text">Run recommendation engine to capture snapshots.</p>
                        ) : (
                            <div className="history-list">
                                {latestRecommendationSnapshot.map((item) => (
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

            <article className="card dashboard-span">
                <h2>Explanation Panel (SHAP/LIME Style)</h2>
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

            <article className="card dashboard-span">
                <div className="panel-header-actions">
                    <h2>RAG Context And Citations</h2>
                    <button className="button secondary" type="button" onClick={ingestDefaultRag} disabled={ragBusy}>
                        {ragBusy ? "Processing..." : "Ingest one_note_extract"}
                    </button>
                </div>
                {ragStatus ? (
                    <div className="metric-grid">
                        <div className="metric-item">
                            <span>RAG Enabled</span>
                            <strong>{String(ragStatus.enabled)}</strong>
                        </div>
                        <div className="metric-item">
                            <span>Total Chunks</span>
                            <strong>{ragStatus.total_chunks}</strong>
                        </div>
                        <div className="metric-item">
                            <span>Ingested Files</span>
                            <strong>{ragStatus.ingested_files?.length || 0}</strong>
                        </div>
                    </div>
                ) : (
                    <p className="muted-text">Loading RAG status...</p>
                )}

                <form className="inline-form" onSubmit={searchRag}>
                    <input value={ragQuery} onChange={(event) => setRagQuery(event.target.value)} placeholder="Search retrieval context" />
                    <button className="button" type="submit" disabled={ragBusy}>
                        Search
                    </button>
                </form>

                <div className="history-list">
                    {ragResults.map((citation, index) => (
                        <article key={`${citation.source}-${index}`} className="history-item">
                            <h4>{citation.title}</h4>
                            <p>{citation.snippet}</p>
                            <small>
                                {citation.source_type}: {citation.source}
                            </small>
                        </article>
                    ))}
                </div>
            </article>

            <article className="card">
                <h2>Real-Time Job Market API</h2>
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
                <div className="history-list">
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

            <article className="card">
                <h2>Psychometric Test Scoring</h2>
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
        </section>
    );
}

export default DashboardPage;
