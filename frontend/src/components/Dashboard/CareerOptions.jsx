function RuntimeSignalsPanel({ llmStatus, xaiStatus, ragStatus }) {
    return (
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
    );
}

function RagSearchPanel({ ragQuery, setRagQuery, searchRag, ragBusy, ragResults }) {
    return (
        <>
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
        </>
    );
}

function MarketDemandPanel({ jobQuery, setJobQuery, loadMarketJobs, jobs, groupedJobs = [] }) {
    return (
        <>
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
                {groupedJobs.length > 0 ? (
                    groupedJobs.map((group) => (
                        <section key={group.role} className="history-item">
                            <h4>Recommended Role: {group.role}</h4>
                            {group.jobs.length === 0 ? (
                                <p className="muted-text">No jobs found for this role right now.</p>
                            ) : (
                                <div className="history-list">
                                    {group.jobs.map((job) => (
                                        <article key={`${group.role}-${job.company}-${job.job_title}`} className="history-item">
                                            <h4>{job.job_title}</h4>
                                            <p>
                                                {job.company} - {job.location}
                                            </p>
                                            <small>{job.category}</small>
                                        </article>
                                    ))}
                                </div>
                            )}
                        </section>
                    ))
                ) : (
                    jobs.map((job) => (
                        <article key={`${job.company}-${job.job_title}`} className="history-item">
                            <h4>{job.job_title}</h4>
                            <p>
                                {job.company} - {job.location}
                            </p>
                            <small>{job.category}</small>
                        </article>
                    ))
                )}
            </div>
        </>
    );
}

export { MarketDemandPanel, RagSearchPanel, RuntimeSignalsPanel };
