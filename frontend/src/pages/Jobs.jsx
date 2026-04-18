import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { MarketDemandPanel } from "../components/Dashboard/CareerOptions";
import CollapsibleCard from "../components/Dashboard/Dashboard";
import { apiClient } from "../services/api";

function JobsPage() {
    const location = useLocation();
    const [jobs, setJobs] = useState([]);
    const [groupedJobs, setGroupedJobs] = useState([]);
    const [jobQuery, setJobQuery] = useState("data scientist");
    const [error, setError] = useState("");
    const [seedRoles, setSeedRoles] = useState([]);
    const [loading, setLoading] = useState(false);
    const [collapsedSections, setCollapsedSections] = useState({
        market: false,
    });

    const toggleSection = (sectionKey) => {
        setCollapsedSections((prev) => ({
            ...prev,
            [sectionKey]: !prev[sectionKey],
        }));
    };

    const loadMarketJobs = async (query) => {
        setError("");
        setSeedRoles([]);
        setGroupedJobs([]);
        setLoading(true);
        try {
            const response = await apiClient.get(`/market/jobs?search=${encodeURIComponent(query)}&limit=12`);
            setJobs(response.data.results || []);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load job market data");
        } finally {
            setLoading(false);
        }
    };

    const loadJobsForRecommendedRoles = async (roles) => {
        setError("");
        setSeedRoles(roles);
        setLoading(true);
        try {
            // Cap at 4 roles max to avoid excessive parallel external calls
            const capped = roles.slice(0, 4);
            const responses = await Promise.all(
                capped.map((role) =>
                    apiClient.get(`/market/jobs?search=${encodeURIComponent(role)}&limit=5`),
                ),
            );

            const grouped = capped.map((role, index) => ({
                role,
                jobs: responses[index].data.results || [],
            }));
            setGroupedJobs(grouped);

            const merged = responses.flatMap((response) => response.data.results || []);
            const deduped = [];
            const seen = new Set();

            for (const job of merged) {
                const key = `${job.job_title || ""}|${job.company || ""}|${job.location || ""}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    deduped.push(job);
                }
            }

            setJobs(deduped);
            setJobQuery(capped.join(", "));
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load job market data for recommended roles");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        let cancelled = false;

        const hydrateInitialQuery = async () => {
            const params = new URLSearchParams(location.search);
            const incomingQuery = params.get("query");

            if (incomingQuery && incomingQuery.trim()) {
                if (!cancelled) {
                    setJobQuery(incomingQuery);
                }
                await loadMarketJobs(incomingQuery);
                return;
            }

            try {
                // Fetch history and feedback in parallel to filter out rejected roles
                const [historyRes, feedbackRes] = await Promise.all([
                    apiClient.get("/recommendations/history/me"),
                    apiClient.get("/recommendations/feedback/me").catch(() => ({ data: { feedback: [] } })),
                ]);

                const history = historyRes.data?.history || [];
                const latestRecommendations = history[0]?.recommendations || [];
                const feedbackItems = feedbackRes.data?.feedback || [];

                // Build a set of roles the user explicitly rejected
                const rejectedRoles = new Set(
                    feedbackItems
                        .filter((f) => f.helpful === false)
                        .map((f) => (f.role || "").toLowerCase()),
                );

                const latestRoles = latestRecommendations
                    .map((item) => item.role)
                    .filter((role) => typeof role === "string" && role.trim())
                    .filter((role) => !rejectedRoles.has(role.toLowerCase()));

                if (!cancelled && latestRoles.length > 0) {
                    await loadJobsForRecommendedRoles(latestRoles);
                    return;
                }
            } catch {
                // Fallback to default search input if recommendation history is unavailable.
            }

            if (!cancelled) {
                await loadMarketJobs(jobQuery);
            }
        };

        hydrateInitialQuery();

        return () => {
            cancelled = true;
        };
    }, [location.search]);

    return (
        <section className="dashboard-stack">
            <section className="card">
                <h1 className="page-heading-row"><span className="page-heading-symbol" aria-hidden="true">💼</span>Live Job Market</h1>
                <p className="muted-text">Independent market demand explorer. Search any role directly without running recommendations first.</p>
                {seedRoles.length > 0 ? (
                    <p className="muted-text">Preloaded from latest recommendation run: {seedRoles.join(", ")}</p>
                ) : null}
            </section>

            {error ? <p className="error-text">{error}</p> : null}
            {loading ? <p className="muted-text" style={{ paddingLeft: "0.5rem" }}>Loading job listings…</p> : null}

            <CollapsibleCard
                sectionKey="market"
                eyebrow="Market Demand"
                title="Search open roles, employers, and locations"
                collapsedSections={collapsedSections}
                toggleSection={toggleSection}
                contentId="jobs-market-content"
                className="card dashboard-primary-panel"
            >
                <MarketDemandPanel
                    jobQuery={jobQuery}
                    setJobQuery={setJobQuery}
                    loadMarketJobs={loadMarketJobs}
                    jobs={jobs}
                    groupedJobs={groupedJobs}
                />
            </CollapsibleCard>
        </section>
    );
}

export default JobsPage;
