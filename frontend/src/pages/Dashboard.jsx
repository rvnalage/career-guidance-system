import { useEffect, useState } from "react";

import ConfirmModal from "../components/Common/ConfirmModal";
import { MarketDemandPanel, RagSearchPanel, RuntimeSignalsPanel } from "../components/Dashboard/CareerOptions";
import CollapsibleCard, { DashboardHero } from "../components/Dashboard/Dashboard";
import { EvidencePanel, ExplanationPanel, RecommendationWorkspace } from "../components/Dashboard/Recommendations";
import { ProfileContextPanel } from "../components/Dashboard/SkillsGapAnalysis";
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
    const [collapsedSections, setCollapsedSections] = useState({
        hero: false,
        recommendations: false,
        explanations: false,
        evidence: false,
        runtimeSignals: false,
        ragSearch: false,
        marketDemand: false,
        psychometric: false,
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
    ].join(" | ");

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

            <section className="dashboard-layout">
                <div className="dashboard-main-column">
                    <CollapsibleCard
                        sectionKey="recommendations"
                        eyebrow="Recommendation Workspace"
                        title="Generate and compare career directions"
                        collapsedSections={collapsedSections}
                        toggleSection={toggleSection}
                        contentId="dashboard-recommendations-content"
                        className="card dashboard-primary-panel"
                        actions={(
                            <button className="button secondary" type="button" onClick={exportDashboardReport}>
                                Export Report JSON
                            </button>
                        )}
                    >
                        <RecommendationWorkspace
                            form={form}
                            setForm={setForm}
                            generateRecommendations={generateRecommendations}
                            effectiveRecommendations={effectiveRecommendations}
                            submitRecommendationFeedback={submitRecommendationFeedback}
                            error={error}
                            setPendingRecommendationClearTarget={setPendingRecommendationClearTarget}
                        />
                    </CollapsibleCard>

                    <CollapsibleCard
                        sectionKey="explanations"
                        eyebrow="Why These Roles"
                        title="Explanation panel"
                        collapsedSections={collapsedSections}
                        toggleSection={toggleSection}
                        contentId="dashboard-explanations-content"
                        className="card dashboard-primary-panel"
                        actions={(
                            <div className="status-chip-row">
                                {xaiStatus ? <span className="status-chip">XAI: {xaiStatus.active_mode}</span> : null}
                                {llmStatus ? <span className="status-chip">LLM: {llmStatus.enabled ? "enabled" : "disabled"}</span> : null}
                            </div>
                        )}
                    >
                        <ExplanationPanel explanations={explanations} />
                    </CollapsibleCard>

                    <CollapsibleCard
                        sectionKey="evidence"
                        eyebrow="Evidence And Continuity"
                        title="Recent activity and last recommendation context"
                        collapsedSections={collapsedSections}
                        toggleSection={toggleSection}
                        contentId="dashboard-evidence-content"
                        className="card dashboard-primary-panel"
                    >
                        <EvidencePanel
                            loadingHistory={loadingHistory}
                            effectiveRecentMessages={effectiveRecentMessages}
                            effectiveRecommendations={effectiveRecommendations}
                        />
                    </CollapsibleCard>
                </div>

                <aside className="dashboard-side-column">
                    <CollapsibleCard
                        sectionKey="runtimeSignals"
                        eyebrow="System Context"
                        title="Runtime signals"
                        collapsedSections={collapsedSections}
                        toggleSection={toggleSection}
                        contentId="dashboard-runtime-content"
                        className="card side-panel"
                    >
                        <RuntimeSignalsPanel llmStatus={llmStatus} xaiStatus={xaiStatus} ragStatus={ragStatus} />
                    </CollapsibleCard>

                    <CollapsibleCard
                        sectionKey="ragSearch"
                        eyebrow="Knowledge Context"
                        title="RAG search"
                        collapsedSections={collapsedSections}
                        toggleSection={toggleSection}
                        contentId="dashboard-rag-content"
                        className="card side-panel"
                        actions={(
                            <button className="button secondary" type="button" onClick={ingestDefaultRag} disabled={ragBusy}>
                                {ragBusy ? "Processing..." : "Ingest Docs"}
                            </button>
                        )}
                    >
                        <RagSearchPanel
                            ragQuery={ragQuery}
                            setRagQuery={setRagQuery}
                            searchRag={searchRag}
                            ragBusy={ragBusy}
                            ragResults={ragResults}
                        />
                    </CollapsibleCard>

                    <CollapsibleCard
                        sectionKey="marketDemand"
                        eyebrow="Market Context"
                        title="Live role demand"
                        collapsedSections={collapsedSections}
                        toggleSection={toggleSection}
                        contentId="dashboard-market-content"
                        className="card side-panel"
                    >
                        <MarketDemandPanel
                            jobQuery={jobQuery}
                            setJobQuery={setJobQuery}
                            loadMarketJobs={loadMarketJobs}
                            jobs={jobs}
                        />
                    </CollapsibleCard>

                    <CollapsibleCard
                        sectionKey="psychometric"
                        eyebrow="Profile Context"
                        title="Psychometric scoring"
                        collapsedSections={collapsedSections}
                        toggleSection={toggleSection}
                        contentId="dashboard-psychometric-content"
                        className="card side-panel"
                    >
                        <ProfileContextPanel
                            ownerType={ownerType}
                            setOwnerType={setOwnerType}
                            uploadBusy={uploadBusy}
                            uploadFiles={uploadFiles}
                            setUploadFiles={setUploadFiles}
                            uploadProfileFiles={uploadProfileFiles}
                            uploadMessage={uploadMessage}
                            psychometric={psychometric}
                            setPsychometric={setPsychometric}
                            scorePsychometric={scorePsychometric}
                            psychometricResult={psychometricResult}
                        />
                    </CollapsibleCard>
                </aside>
            </section>

            <ConfirmModal
                open={Boolean(pendingRecommendationClearTarget)}
                title="Confirm Clear"
                message={pendingRecommendationClearTarget === "backend"
                    ? "Confirm clear of saved recommendation history from backend?"
                    : "Confirm clear of recommendation results visible in this dashboard?"}
                confirmLabel="Confirm Clear"
                onConfirm={confirmRecommendationClear}
                onCancel={() => setPendingRecommendationClearTarget(null)}
            />
        </section>
    );
}

export default DashboardPage;
