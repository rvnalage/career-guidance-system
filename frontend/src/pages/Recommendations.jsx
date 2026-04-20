import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import ConfirmModal from "../components/Common/ConfirmModal";
import CollapsibleCard from "../components/Dashboard/Dashboard";
import { RecommendationWorkspace } from "../components/Dashboard/Recommendations";
import { apiClient } from "../services/api";

const initialForm = {
    interests: "AI, Data Science",
    skills: "Python, Machine Learning, SQL",
    education_level: "master",
};

function RecommendationsPage({ isAuthenticated }) {
    const [form, setForm] = useState(initialForm);
    const [recommendations, setRecommendations] = useState([]);
    const [recommendationHistory, setRecommendationHistory] = useState([]);
    const [explanations, setExplanations] = useState([]);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const [loadingHistory, setLoadingHistory] = useState(false);
    const [pendingRecommendationClearTarget, setPendingRecommendationClearTarget] = useState(null);
    const [collapsedSections, setCollapsedSections] = useState({
        generator: false,
        results: false,
        history: false,
    });

    const toggleSection = (sectionKey) => {
        setCollapsedSections((prev) => ({
            ...prev,
            [sectionKey]: !prev[sectionKey],
        }));
    };

    const loadRecommendationHistory = async () => {
        setLoadingHistory(true);
        try {
            const recommendationResponse = await apiClient.get("/recommendations/history/me");
            setRecommendationHistory(recommendationResponse.data.history || []);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load history");
        } finally {
            setLoadingHistory(false);
        }
    };

    useEffect(() => {
        if (isAuthenticated) {
            loadRecommendationHistory();
        }
    }, [isAuthenticated]);

    const generateRecommendations = async (event) => {
        event.preventDefault();
        setError("");
        setBusy(true);
        try {
            const response = await apiClient.post("/recommendations/generate", {
                interests: form.interests.split(",").map((item) => item.trim()).filter(Boolean),
                skills: form.skills.split(",").map((item) => item.trim()).filter(Boolean),
                education_level: form.education_level,
            });
            setRecommendations(response.data.recommendations || []);

            await loadExplanationPanel();
            await loadRecommendationHistory();
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to generate recommendations");
        } finally {
            setBusy(false);
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
            setError(err.response?.data?.detail || "Could not generate explanations");
        }
    };

    const [feedbackSubmitted, setFeedbackSubmitted] = useState({});

    const submitRecommendationFeedback = async (role, helpful) => {
        try {
            await apiClient.post("/recommendations/feedback/me", {
                role,
                helpful,
                rating: helpful ? 5 : 2,
                feedback_tags: ["clarity", "relevance"],
            });
            setFeedbackSubmitted((prev) => ({ ...prev, [role]: helpful ? "helpful" : "not_helpful" }));
        } catch (err) {
            setError(err.response?.data?.detail || "Could not submit feedback");
        }
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
            await loadRecommendationHistory();
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

    const mostRecentRecommendationRun = recommendationHistory[0];
    const explanationByRole = new Map(
        explanations.map((item) => [item.role, item]),
    );

    return (
        <section className="dashboard-stack">
            <section className="card">
                <h1 className="page-heading-row"><span className="page-heading-symbol" aria-hidden="true">🎯</span>Recommendations</h1>
                <p className="muted-text">Generate personalized career recommendations and understand your career fit with clear scoring insights.</p>
            </section>

            {error ? <div className="error-message">{error}</div> : null}

            <section className="dashboard-layout">
                <div className="dashboard-main-column">
                    {/* Generator Section */}
                    <CollapsibleCard
                        sectionKey="generator"
                        eyebrow="Career Engine"
                        title="Generate recommendations"
                        collapsedSections={collapsedSections}
                        toggleSection={toggleSection}
                        contentId="recommendations-generator-content"
                        className="card dashboard-primary-panel"
                    >
                        <RecommendationWorkspace
                            form={form}
                            setForm={setForm}
                            generateRecommendations={generateRecommendations}
                            busy={busy}
                            effectiveRecommendations={[]}
                            submitRecommendationFeedback={submitRecommendationFeedback}
                            error={error}
                            setPendingRecommendationClearTarget={setPendingRecommendationClearTarget}
                        />
                    </CollapsibleCard>

                    {/* Results + Insights (single combined section) */}
                    {recommendations.length > 0 || explanations.length > 0 ? (
                        <CollapsibleCard
                            sectionKey="results"
                            eyebrow="Recommendation Results"
                            title="Top matches, confidence, and role-wise XAI weights"
                            collapsedSections={collapsedSections}
                            toggleSection={toggleSection}
                            contentId="recommendations-results-content"
                            className="card dashboard-primary-panel"
                        >
                            {recommendations.length > 0 ? (
                                <>
                                    <div className="result-summary-strip">
                                        <div className="result-summary-item">
                                            <span>Total roles</span>
                                            <strong>{recommendations.length}</strong>
                                        </div>
                                        <div className="result-summary-item">
                                            <span>Top match</span>
                                            <strong>{recommendations[0]?.role || "N/A"}</strong>
                                        </div>
                                        <div className="result-summary-item">
                                            <span>Average confidence</span>
                                            <strong>
                                                {(
                                                    recommendations.reduce((acc, item) => acc + (item.confidence || 0), 0)
                                                    / recommendations.length
                                                    * 100
                                                ).toFixed(1)}%
                                            </strong>
                                        </div>
                                    </div>

                                    <div className="recommendation-list">
                                        {recommendations.map((item, idx) => (
                                            <article key={item.role} className="recommendation-item">
                                                <div className="recommendation-header">
                                                    <h4>
                                                        <span className="recommendation-rank-chip">#{idx + 1}</span>
                                                        <span>{item.role}</span>
                                                    </h4>
                                                    <div className="confidence-badge">
                                                        <div className="confidence-bar" style={{ width: `${item.confidence * 100}%` }} />
                                                        <span className="confidence-text">{(item.confidence * 100).toFixed(0)}%</span>
                                                    </div>
                                                </div>
                                                <p className="recommendation-reason"><strong>Why this role:</strong> {item.reason}</p>

                                                {item.skill_gaps?.length ? (
                                                    <div className="xai-role-weights" style={{ marginTop: "0.6rem" }}>
                                                        <p className="xai-title">Skill Gaps</p>
                                                        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                                                            {item.skill_gaps.map((gap) => (
                                                                <span
                                                                    key={`${item.role}-gap-${gap}`}
                                                                    style={{
                                                                        display: "inline-flex",
                                                                        alignItems: "center",
                                                                        padding: "0.2rem 0.55rem",
                                                                        borderRadius: "999px",
                                                                        background: "rgba(245, 158, 11, 0.14)",
                                                                        border: "1px solid rgba(245, 158, 11, 0.35)",
                                                                        fontSize: "0.78rem",
                                                                        fontWeight: 500,
                                                                    }}
                                                                >
                                                                    {gap}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                ) : null}

                                                {item.upgrade_suggestions?.length ? (
                                                    <div className="xai-role-weights" style={{ marginTop: "0.6rem" }}>
                                                        <p className="xai-title">Upgrade Suggestions</p>
                                                        <ul className="msg-list" style={{ marginTop: "0.35rem" }}>
                                                            {item.upgrade_suggestions.map((suggestion) => (
                                                                <li key={`${item.role}-up-${suggestion}`}>{suggestion}</li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                ) : null}

                                                {explanationByRole.get(item.role)?.contributions?.length ? (
                                                    <div className="xai-role-weights">
                                                        <p className="xai-title">XAI Weights ({explanationByRole.get(item.role).label})</p>
                                                        {explanationByRole.get(item.role).contributions.map((contribution) => (
                                                            <div key={`${item.role}-${contribution.feature}`} className="xai-weight-row">
                                                                <div className="xai-weight-head">
                                                                    <span>{contribution.feature}</span>
                                                                    <strong>{(contribution.value * 100).toFixed(1)}%</strong>
                                                                </div>
                                                                <div className="xai-weight-track" aria-hidden="true">
                                                                    <div
                                                                        className="xai-weight-fill"
                                                                        style={{ width: `${Math.max(0, Math.min(100, contribution.value * 100))}%` }}
                                                                    />
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <p className="muted-text" style={{ marginTop: "0.55rem" }}>
                                                        XAI weights will appear here after explanation data is available for this role.
                                                    </p>
                                                )}

                                                <div className="feedback-row">
                                                    {feedbackSubmitted[item.role] ? (
                                                        <span className="feedback-sent-badge">
                                                            {feedbackSubmitted[item.role] === "helpful" ? "👍 Thanks for your feedback!" : "👎 Noted — we'll improve this."}
                                                        </span>
                                                    ) : (
                                                        <>
                                                            <button
                                                                className="button secondary"
                                                                type="button"
                                                                onClick={() => {
                                                                    submitRecommendationFeedback(item.role, true);
                                                                }}
                                                            >
                                                                👍 Helpful
                                                            </button>
                                                            <button
                                                                className="button ghost"
                                                                type="button"
                                                                onClick={() => {
                                                                    submitRecommendationFeedback(item.role, false);
                                                                }}
                                                            >
                                                                👎 Not Helpful
                                                            </button>
                                                        </>
                                                    )}
                                                    <Link className="button ghost button-job-link" to={`/jobs?query=${encodeURIComponent(item.role)}`}>
                                                        Open in Jobs Tab
                                                    </Link>
                                                </div>
                                            </article>
                                        ))}
                                    </div>
                                </>
                            ) : null}
                        </CollapsibleCard>
                    ) : null}

                </div>

                <aside className="dashboard-side-column">
                    {/* Recommendation History (always independent of explanations) */}
                    {recommendationHistory.length > 0 ? (
                        <CollapsibleCard
                            sectionKey="history"
                            eyebrow="Recommendation History"
                            title="Your saved recommendation run history"
                            collapsedSections={collapsedSections}
                            toggleSection={toggleSection}
                            contentId="recommendations-history-content"
                            className="card side-panel"
                        >
                            <div className="stats-grid">
                                <div className="stat-item">
                                    <p>Total Recommendation Runs</p>
                                    <strong>{loadingHistory ? "..." : recommendationHistory.length}</strong>
                                </div>
                                <div className="stat-item">
                                    <p>Unique Roles Suggested</p>
                                    <strong>{loadingHistory ? "..." : new Set(recommendationHistory.flatMap((r) => r.recommendations.map((rec) => rec.role))).size}</strong>
                                </div>
                                <div className="stat-item">
                                    <p>Last Recommendation Run (Date & Time)</p>
                                    <strong>{mostRecentRecommendationRun ? new Date(mostRecentRecommendationRun.generated_at).toLocaleString() : "N/A"}</strong>
                                    {mostRecentRecommendationRun?.recommendations?.length > 0 && (
                                        <div style={{ marginTop: "0.8rem" }}>
                                            <p className="muted-text" style={{ marginBottom: "0.4rem", fontSize: "0.82rem" }}>Last run — top roles:</p>
                                            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                                                {mostRecentRecommendationRun.recommendations.slice(0, 6).map((rec) => (
                                                    <span
                                                        key={rec.role}
                                                        style={{
                                                            display: "inline-flex",
                                                            alignItems: "center",
                                                            gap: "0.25rem",
                                                            padding: "0.22rem 0.6rem",
                                                            borderRadius: "999px",
                                                            background: "linear-gradient(135deg, rgba(15,118,110,0.1), rgba(37,99,235,0.08))",
                                                            border: "1px solid rgba(15,118,110,0.25)",
                                                            fontSize: "0.78rem",
                                                            fontWeight: 500,
                                                            color: "var(--accent)",
                                                        }}
                                                    >
                                                        {(rec.confidence * 100).toFixed(0)}% {rec.role}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </CollapsibleCard>
                    ) : (
                        <section className="card side-panel">
                            <div className="collapsible-card-header">
                                <h3>Recommendation History</h3>
                            </div>
                            <p className="muted-text">No recommendation runs yet. Run the engine to start building history.</p>
                        </section>
                    )}
                </aside>
            </section>

            <ConfirmModal
                open={Boolean(pendingRecommendationClearTarget)}
                title="Confirm Clear"
                message={pendingRecommendationClearTarget === "backend"
                    ? "Clear all saved recommendation history? This action cannot be undone."
                    : "Clear recommendations from this view?"}
                confirmLabel="Confirm Clear"
                onConfirm={confirmRecommendationClear}
                onCancel={() => setPendingRecommendationClearTarget(null)}
            />
        </section>
    );
}

export default RecommendationsPage;
