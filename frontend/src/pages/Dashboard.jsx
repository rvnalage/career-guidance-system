import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { DashboardHero } from "../components/Dashboard/Dashboard";
import { apiClient } from "../services/api";

function DashboardPage() {
    const [summary, setSummary] = useState(null);
    const [chatHistory, setChatHistory] = useState([]);
    const [recommendationHistory, setRecommendationHistory] = useState([]);
    const [psychometricStatus, setPsychometricStatus] = useState(null);
    const [error, setError] = useState("");
    const [collapsedSections, setCollapsedSections] = useState({
        hero: false,
    });

    const toggleSection = (sectionKey) => {
        setCollapsedSections((prev) => ({
            ...prev,
            [sectionKey]: !prev[sectionKey],
        }));
    };

    const loadSummary = async () => {
        try {
            const response = await apiClient.get("/dashboard/summary/me");
            setSummary(response.data);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load dashboard summary");
        }
    };

    useEffect(() => {
        loadSummary();
        loadSignals();
    }, []);

    const loadSignals = async () => {
        try {
            const [chatResponse, recommendationResponse, psychometricResponse] = await Promise.all([
                apiClient.get("/history/me"),
                apiClient.get("/recommendations/history/me"),
                apiClient.get("/psychometric/profile/me").catch(() => ({ data: null })),
            ]);
            setChatHistory(chatResponse.data.messages || []);
            setRecommendationHistory(recommendationResponse.data.history || []);
            setPsychometricStatus(psychometricResponse.data || null);
        } catch {
            // Dashboard should stay usable even if one of the optional signals fails.
        }
    };

    const recommendationRuns = Number(summary?.recommendation_runs || 0);
    const conversationTurns = Number(summary?.conversation_turns || 0);
    const nextAction = summary?.next_action || "Open Recommendations and run a fresh role match";
    const topRolesText = summary?.top_roles?.length ? summary.top_roles.join(", ") : "No roles shortlisted yet";
    const profileSignals = `${summary?.profile_completion ?? "--"}% profile completion`;
    const profileCompletion = Number(summary?.profile_completion || 0);
    const latestRecommendation = recommendationHistory[0]?.recommendations?.[0] || null;
    const lastRecommendationTime = recommendationHistory[0]?.generated_at;
    const recommendationAgeDays = lastRecommendationTime
        ? Math.floor((Date.now() - new Date(lastRecommendationTime).getTime()) / (1000 * 60 * 60 * 24))
        : null;
    const hasPsychometric = Boolean(psychometricStatus?.normalized_scores && Object.keys(psychometricStatus.normalized_scores).length > 0);

    const getNextBestAction = () => {
        if (profileCompletion < 70) {
            return {
                label: "Complete Profile",
                route: "/profile",
                reason: "Better profile signals improve recommendation quality.",
            };
        }
        if (!hasPsychometric) {
            return {
                label: "Take Psychometric Assessment",
                route: "/profile",
                reason: "Psychometric signals unlock stronger role matching.",
            };
        }
        if (recommendationRuns === 0) {
            return {
                label: "Generate Recommendations",
                route: "/recommendations",
                reason: "No recommendation run found yet.",
            };
        }
        if (recommendationAgeDays !== null && recommendationAgeDays > 7) {
            return {
                label: "Refresh Recommendations",
                route: "/recommendations",
                reason: "Your last recommendation run is older than a week.",
            };
        }
        return {
            label: "Explore Jobs",
            route: "/jobs",
            reason: "Your guidance signals look good. Start shortlisting roles.",
        };
    };

    const nextBestAction = getNextBestAction();

    const readinessScore = Math.min(100,
        Math.round(
            (profileCompletion * 0.45)
            + (hasPsychometric ? 20 : 0)
            + (recommendationRuns > 0 ? 20 : 0)
            + (conversationTurns > 0 ? 15 : 0),
        ),
    );

    const activityEvents = [
        ...chatHistory.slice(-4).map((entry, idx) => ({
            type: "Chat",
            text: entry.text || entry.message || "Conversation updated",
            at: entry.created_at || entry.timestamp || null,
            key: `chat-${idx}`,
        })),
        ...recommendationHistory.slice(0, 3).map((run, idx) => ({
            type: "Recommendation",
            text: `Generated ${run.recommendations?.length || 0} role suggestions`,
            at: run.generated_at || null,
            key: `reco-${idx}`,
        })),
    ]
        .sort((a, b) => new Date(b.at || 0).getTime() - new Date(a.at || 0).getTime())
        .slice(0, 5);
    const recentChatHistory = [...chatHistory]
        .slice(-8)
        .reverse()
        .map((entry, idx) => ({
            key: `history-${idx}`,
            role: entry.role || "assistant",
            text: entry.text || entry.message || "No content",
            at: entry.created_at || entry.timestamp || null,
        }));

    return (
        <section className="dashboard-stack">
            <DashboardHero
                summary={summary}
                topRolesText={topRolesText}
                nextAction={nextAction}
                profileSignals={profileSignals}
                conversationTurns={conversationTurns}
                recommendationRuns={recommendationRuns}
                collapsedSections={collapsedSections}
                toggleSection={toggleSection}
            />

            <section className="dashboard-grid dashboard-action-grid">
                <article className="card dashboard-widget-card">
                    <p className="eyebrow">Next Best Action</p>
                    <h3>{nextBestAction.label}</h3>
                    <p className="muted-text">{nextBestAction.reason}</p>
                    <Link className="button" to={nextBestAction.route}>{nextBestAction.label}</Link>
                </article>

                <article className="card dashboard-widget-card">
                    <p className="eyebrow">Career Readiness</p>
                    <h3>{readinessScore}/100</h3>
                    <div className="readiness-track" aria-hidden="true">
                        <div className="readiness-fill" style={{ width: `${readinessScore}%` }} />
                    </div>
                    <p className="muted-text">Based on profile completeness, psychometric status, recommendations, and chat activity.</p>
                </article>

                <article className="card dashboard-widget-card">
                    <p className="eyebrow">Role Focus</p>
                    <h3>{latestRecommendation?.role || "No top role yet"}</h3>
                    <p className="muted-text">
                        {latestRecommendation
                            ? `Confidence ${(latestRecommendation.confidence * 100).toFixed(0)}%`
                            : "Run recommendations to generate your top role focus."}
                    </p>
                    <div className="cta-row">
                        <Link className="button secondary" to="/recommendations">Open Recommendations</Link>
                        <Link className="button ghost" to="/jobs">Explore Jobs</Link>
                    </div>
                </article>

                <article className="card dashboard-widget-card">
                    <p className="eyebrow">Recent Progress</p>
                    <h3>Latest activity timeline</h3>
                    <div className="history-list">
                        {activityEvents.length > 0 ? (
                            activityEvents.map((item) => (
                                <article key={item.key} className="history-item">
                                    <small>{item.type}</small>
                                    <p>{item.text}</p>
                                    {item.at ? <span className="muted-text">{new Date(item.at).toLocaleString()}</span> : null}
                                </article>
                            ))
                        ) : (
                            <p className="muted-text">No recent activity yet. Start with Profile or Recommendations.</p>
                        )}
                    </div>
                </article>
            </section>

            <section className="card dashboard-widget-card">
                <p className="eyebrow">Chat History</p>
                <h3>Recent conversations</h3>
                <div className="chat-history-grid">
                    {recentChatHistory.length > 0 ? (
                        recentChatHistory.map((item) => (
                            <article key={item.key} className={`chat-history-item ${item.role}`}>
                                <div className="chat-history-head">
                                    <span className={`chat-role-pill ${item.role}`}>{item.role === "user" ? "You" : "Assistant"}</span>
                                    {item.at ? <small>{new Date(item.at).toLocaleString()}</small> : null}
                                </div>
                                <p>{item.text}</p>
                            </article>
                        ))
                    ) : (
                        <p className="muted-text">No chat history yet. Start a conversation in Chat.</p>
                    )}
                </div>
            </section>

            {error ? <div className="error-message">{error}</div> : null}
        </section>
    );
}

export default DashboardPage;
