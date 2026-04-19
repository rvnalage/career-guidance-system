import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import PlannerTrace from "../components/Chat/PlannerTrace";
import { DashboardHero } from "../components/Dashboard/Dashboard";
import { apiClient } from "../services/api";

function DashboardPage() {
    const [orchestrationWindow, setOrchestrationWindow] = useState("7d");
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
    const parseEntryTime = (entry) => {
        const raw = entry.created_at || entry.timestamp;
        const parsed = raw ? new Date(raw).getTime() : Number.NaN;
        return Number.isFinite(parsed) ? parsed : null;
    };
    const tracedAssistantAll = chatHistory.filter((entry) => entry.role === "assistant" && entry.planner_steps?.length);
    const now = Date.now();
    const tracedAssistantReplies = tracedAssistantAll.filter((entry) => {
        if (orchestrationWindow === "all") {
            return true;
        }
        if (orchestrationWindow === "20runs") {
            return true;
        }
        const timestamp = parseEntryTime(entry);
        if (!timestamp) {
            return false;
        }
        if (orchestrationWindow === "30d") {
            return timestamp >= (now - (30 * 24 * 60 * 60 * 1000));
        }
        return timestamp >= (now - (7 * 24 * 60 * 60 * 1000));
    });
    const scopedTracedReplies = orchestrationWindow === "20runs"
        ? tracedAssistantReplies.slice(-20)
        : tracedAssistantReplies;
    const latestAgentTrace = [...scopedTracedReplies].reverse()[0] || null;
    const latestPlannerSteps = latestAgentTrace?.planner_steps || [];
    const toolStepCount = latestPlannerSteps.filter((step) => String(step.name || "").endsWith("_tool")).length;
    const supportStepCount = latestPlannerSteps.filter((step) => String(step.name || "").startsWith("support_")).length;
    const intentStep = latestPlannerSteps.find((step) => String(step.name || "").startsWith("primary_"));
    const currentIntent = intentStep?.name
        ? intentStep.name.replace("primary_", "").replaceAll("_", " ")
        : "No routed intent yet";
    const windowLabelMap = {
        "7d": "Last 7 Days",
        "30d": "Last 30 Days",
        "20runs": "Last 20 Traces",
        all: "All Time",
    };
    const activeWindowLabel = windowLabelMap[orchestrationWindow] || "Last 7 Days";
    const traceTimestamp = latestAgentTrace?.created_at || latestAgentTrace?.timestamp || null;
    const tracePreview = latestAgentTrace?.text || latestAgentTrace?.message || "";
    const latestPlanId = latestAgentTrace?.plan_id || null;
    const latestPlannerDuration = Number(latestAgentTrace?.planner_duration_ms || 0);
    const latestOutcomeScores = latestAgentTrace?.outcome_scores || [];
    const averagePlannerDepth = scopedTracedReplies.length
        ? (scopedTracedReplies.reduce((total, entry) => total + (entry.planner_steps?.length || 0), 0) / scopedTracedReplies.length)
        : 0;
    const totalToolCalls = scopedTracedReplies.reduce(
        (total, entry) => total + (entry.planner_steps || []).filter((step) => String(step.name || "").endsWith("_tool")).length,
        0,
    );
    const verifierAdjustments = scopedTracedReplies.filter((entry) => entry.critic_changed).length;
    const intentCounts = scopedTracedReplies.reduce((counts, entry) => {
        const primaryStep = (entry.planner_steps || []).find((step) => String(step.name || "").startsWith("primary_"));
        if (!primaryStep?.name) {
            return counts;
        }
        const intentName = primaryStep.name.replace("primary_", "").replaceAll("_", " ");
        counts[intentName] = (counts[intentName] || 0) + 1;
        return counts;
    }, {});
    const topIntents = Object.entries(intentCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3);
    const toolCounts = scopedTracedReplies.reduce((counts, entry) => {
        (entry.planner_steps || [])
            .filter((step) => String(step.name || "").endsWith("_tool"))
            .forEach((step) => {
                const toolName = String(step.name || "").replaceAll("_", " ");
                counts[toolName] = (counts[toolName] || 0) + 1;
            });
        return counts;
    }, {});
    const topTools = Object.entries(toolCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 4);
    const criticIssueCounts = scopedTracedReplies.reduce((counts, entry) => {
        (entry.critic_issues || []).forEach((issue) => {
            const issueName = String(issue || "").replaceAll("_", " ");
            counts[issueName] = (counts[issueName] || 0) + 1;
        });
        return counts;
    }, {});
    const topCriticIssues = Object.entries(criticIssueCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3);
    const flattenedOutcomeScores = scopedTracedReplies.flatMap((entry) => entry.outcome_scores || []);
    const averageOutcomeScore = flattenedOutcomeScores.length
        ? (flattenedOutcomeScores.reduce((total, item) => total + Number(item.score || 0), 0) / flattenedOutcomeScores.length)
        : 0;
    const outcomeByIntent = flattenedOutcomeScores.reduce((scores, item) => {
        const intentName = String(item.intent || "unknown").replaceAll("_", " ");
        if (!scores[intentName]) {
            scores[intentName] = [];
        }
        scores[intentName].push(Number(item.score || 0));
        return scores;
    }, {});
    // Compute per-intent outcome trends by splitting scored replies into first/second halves
    const scoredReplies = scopedTracedReplies.filter((entry) => (entry.outcome_scores || []).length > 0);
    const half = Math.ceil(scoredReplies.length / 2);
    const firstHalf = scoredReplies.slice(0, half);
    const secondHalf = scoredReplies.slice(half);
    const avgScoreForReplies = (replies, intentName) => {
        const scores = replies.flatMap((entry) =>
            (entry.outcome_scores || [])
                .filter((item) => String(item.intent || "").replaceAll("_", " ") === intentName)
                .map((item) => Number(item.score || 0)),
        );
        return scores.length ? scores.reduce((sum, s) => sum + s, 0) / scores.length : null;
    };
    const intentOutcomeTrend = Object.keys(outcomeByIntent).map((intentName) => {
        const early = avgScoreForReplies(firstHalf, intentName);
        const late = avgScoreForReplies(secondHalf, intentName);
        const avg = outcomeByIntent[intentName].length
            ? outcomeByIntent[intentName].reduce((sum, s) => sum + s, 0) / outcomeByIntent[intentName].length
            : 0;
        let direction = "stable";
        if (early !== null && late !== null) {
            if (late - early > 4) direction = "improving";
            else if (early - late > 4) direction = "declining";
        }
        return { intentName, avg, direction, early, late };
    }).sort((a, b) => b.avg - a.avg).slice(0, 5);

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

            <section className="card dashboard-widget-card orchestration-card">
                <p className="eyebrow">Agent Orchestration</p>
                <h3>{latestPlannerSteps.length ? `${latestPlannerSteps.length} planner steps on latest traced reply` : `No planner trace recorded in ${activeWindowLabel.toLowerCase()}`}</h3>
                <div className="orchestration-window-row" role="group" aria-label="Orchestration analytics window">
                    <button type="button" className={`window-chip${orchestrationWindow === "7d" ? " active" : ""}`} onClick={() => setOrchestrationWindow("7d")}>Last 7 days</button>
                    <button type="button" className={`window-chip${orchestrationWindow === "30d" ? " active" : ""}`} onClick={() => setOrchestrationWindow("30d")}>Last 30 days</button>
                    <button type="button" className={`window-chip${orchestrationWindow === "20runs" ? " active" : ""}`} onClick={() => setOrchestrationWindow("20runs")}>Last 20 traces</button>
                    <button type="button" className={`window-chip${orchestrationWindow === "all" ? " active" : ""}`} onClick={() => setOrchestrationWindow("all")}>All time</button>
                </div>
                {latestAgentTrace ? (
                    <>
                        <div className="orchestration-stats-grid">
                            <article className="orchestration-stat-card">
                                <span className="orchestration-stat-label">Traced replies</span>
                                <strong>{scopedTracedReplies.length}</strong>
                            </article>
                            <article className="orchestration-stat-card">
                                <span className="orchestration-stat-label">Avg planner depth</span>
                                <strong>{averagePlannerDepth.toFixed(1)}</strong>
                            </article>
                            <article className="orchestration-stat-card">
                                <span className="orchestration-stat-label">Total tool calls</span>
                                <strong>{totalToolCalls}</strong>
                            </article>
                            <article className="orchestration-stat-card">
                                <span className="orchestration-stat-label">Verifier edits</span>
                                <strong>{verifierAdjustments}</strong>
                            </article>
                            <article className="orchestration-stat-card">
                                <span className="orchestration-stat-label">Avg outcome score</span>
                                <strong>{averageOutcomeScore ? averageOutcomeScore.toFixed(1) : "-"}</strong>
                            </article>
                        </div>
                        <div className="dashboard-pill-row orchestration-pill-row">
                            <span className="dashboard-pill">Intent: {currentIntent}</span>
                            <span className="dashboard-pill">Tool calls: {toolStepCount}</span>
                            <span className="dashboard-pill">Handoffs: {supportStepCount}</span>
                            {traceTimestamp ? <span className="dashboard-pill">Updated: {new Date(traceTimestamp).toLocaleString()}</span> : null}
                        </div>
                        <div className="orchestration-breakdown-grid">
                            <div className="orchestration-breakdown-panel">
                                <p className="trace-heading">Top Intents</p>
                                {topIntents.length ? (
                                    <div className="orchestration-list">
                                        {topIntents.map(([intentName, count]) => (
                                            <div key={intentName} className="orchestration-list-item">
                                                <span>{intentName}</span>
                                                <strong>{count}</strong>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="muted-text">No routed intents recorded yet.</p>
                                )}
                            </div>
                            <div className="orchestration-breakdown-panel">
                                <p className="trace-heading">Tool Frequency</p>
                                {topTools.length ? (
                                    <div className="orchestration-list">
                                        {topTools.map(([toolName, count]) => (
                                            <div key={toolName} className="orchestration-list-item">
                                                <span>{toolName}</span>
                                                <strong>{count}</strong>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="muted-text">No planner tool calls recorded yet.</p>
                                )}
                            </div>
                            <div className="orchestration-breakdown-panel">
                                <p className="trace-heading">Verifier Issues</p>
                                {topCriticIssues.length ? (
                                    <div className="orchestration-list">
                                        {topCriticIssues.map(([issueName, count]) => (
                                            <div key={issueName} className="orchestration-list-item">
                                                <span>{issueName}</span>
                                                <strong>{count}</strong>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="muted-text">Verifier has not flagged issues in stored replies yet.</p>
                                )}
                            </div>
                            <div className="orchestration-breakdown-panel">
                                <p className="trace-heading">Outcome by Intent</p>
                                {intentOutcomeTrend.length ? (
                                    <div className="orchestration-list outcome-trend-list">
                                        {intentOutcomeTrend.map((item) => (
                                            <div key={item.intentName} className="orchestration-list-item outcome-trend-item">
                                                <span className="outcome-trend-label">{item.intentName}</span>
                                                <div className="outcome-trend-bar-wrap">
                                                    <div
                                                        className="outcome-trend-bar"
                                                        style={{ width: `${Math.min(100, item.avg)}%` }}
                                                        aria-label={`Score ${item.avg.toFixed(1)}`}
                                                    />
                                                </div>
                                                <span className={`outcome-trend-dir outcome-trend-dir--${item.direction}`}>
                                                    {item.direction === "improving" ? "↑" : item.direction === "declining" ? "↓" : "→"}
                                                    {" "}{item.avg.toFixed(0)}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="muted-text">No evaluator scores captured in this window yet.</p>
                                )}
                            </div>
                        </div>
                        <p className="muted-text orchestration-preview">{tracePreview}</p>
                        <PlannerTrace
                            steps={latestPlannerSteps}
                            criticChanged={Boolean(latestAgentTrace?.critic_changed)}
                            criticIssues={latestAgentTrace?.critic_issues || []}
                            planId={latestPlanId}
                            planVariant={latestAgentTrace?.plan_variant || null}
                            planVariantReason={latestAgentTrace?.plan_variant_reason || null}
                            plannerDurationMs={latestPlannerDuration}
                            outcomeScores={latestOutcomeScores}
                            variant="panel"
                        />
                        <div className="cta-row">
                            <Link className="button secondary" to="/chat">Inspect Live Chat</Link>
                            <Link className="button ghost" to="/recommendations">Open Recommendations</Link>
                        </div>
                    </>
                ) : (
                    <>
                        <p className="muted-text">Send a new chat message to capture the planner route, tool usage, and verifier status here.</p>
                        <div className="cta-row">
                            <Link className="button" to="/chat">Open Chat</Link>
                        </div>
                    </>
                )}
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
