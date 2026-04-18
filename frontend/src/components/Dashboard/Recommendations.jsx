function RecommendationWorkspace({
    form,
    setForm,
    generateRecommendations,
    busy,
    effectiveRecommendations,
    submitRecommendationFeedback,
    error,
    setPendingRecommendationClearTarget,
}) {
    return (
        <>
            <p className="muted-text section-copy">
                Update your active skills, interests, and education context. For comprehensive profile management, resume uploads, and complete psychometric assessment, visit the <strong>Profile</strong> tab.
            </p>
            <form onSubmit={generateRecommendations} className="reco-engine-form">
                <label className="reco-field">
                    <span className="reco-field-label">🎯 Interests</span>
                    <input
                        value={form.interests}
                        onChange={(event) => setForm((prev) => ({ ...prev, interests: event.target.value }))}
                        placeholder="e.g. AI, Data Science, Research"
                    />
                    <span className="reco-field-hint">Comma-separated career interests</span>
                </label>
                <label className="reco-field">
                    <span className="reco-field-label">💼 Skills</span>
                    <input
                        value={form.skills}
                        onChange={(event) => setForm((prev) => ({ ...prev, skills: event.target.value }))}
                        placeholder="e.g. Python, Machine Learning, SQL"
                    />
                    <span className="reco-field-hint">Comma-separated technical and soft skills</span>
                </label>
                <label className="reco-field">
                    <span className="reco-field-label">🎓 Education Level</span>
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
                </label>
                <div className="reco-action-row">
                    <button className="button reco-run-btn" type="submit" disabled={busy}>
                        {busy ? (
                            <span className="reco-loading-text">
                                <span className="reco-spinner" aria-hidden="true" /> Running Engine…
                            </span>
                        ) : "🚀 Run Recommendation Engine"}
                    </button>
                    <button className="button ghost reco-secondary-btn" type="button" onClick={() => setPendingRecommendationClearTarget("backend")}>
                        🗑 Clear History
                    </button>
                </div>
            </form>

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
        </>
    );
}

function ExplanationPanel({ explanations }) {
    if (explanations.length === 0) {
        return <p className="muted-text">Generate recommendations to view feature contribution explanations.</p>;
    }

    return (
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
    );
}

function EvidencePanel({ loadingHistory, effectiveRecentMessages, effectiveRecommendations }) {
    return (
        <>
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
        </>
    );
}

export { EvidencePanel, ExplanationPanel, RecommendationWorkspace };
