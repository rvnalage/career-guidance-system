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
        try {
            const response = await apiClient.get(`/market/jobs?search=${encodeURIComponent(query)}&limit=12`);
            setJobs(response.data.results || []);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load job market data");
        }
    };

    const loadJobsForRecommendedRoles = async (roles) => {
        setError("");
        setSeedRoles(roles);
        try {
            const responses = await Promise.all(
                roles.map((role) =>
                    apiClient.get(`/market/jobs?search=${encodeURIComponent(role)}&limit=8`),
                ),
            );

            const grouped = roles.map((role, index) => ({
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
            setJobQuery(roles.join(", "));
        } catch (err) {
            setError(err.response?.data?.detail || "Could not load job market data for recommended roles");
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
                const response = await apiClient.get("/recommendations/history/me");
                const history = response.data?.history || [];
                const latestRecommendations = history[0]?.recommendations || [];
                const latestRoles = latestRecommendations
                    .map((item) => item.role)
                    .filter((role) => typeof role === "string" && role.trim());

                if (latestRoles.length > 0) {
                    await loadJobsForRecommendedRoles(latestRoles);
                    return;
                }
            } catch {
                // Fallback to default search input if recommendation history is unavailable.
            }

            await loadMarketJobs(jobQuery);
        };

        hydrateInitialQuery();

        return () => {
            cancelled = true;
        };
    }, [location.search]);

    return (
        <section className="dashboard-stack">
            <section className="card">
                <h1>Live Job Market</h1>
                <p className="muted-text">Independent market demand explorer. Search any role directly without running recommendations first.</p>
                {seedRoles.length > 0 ? (
                    <p className="muted-text">Preloaded from latest recommendation run: {seedRoles.join(", ")}</p>
                ) : null}
            </section>

            {error ? <p className="error-text">{error}</p> : null}

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
