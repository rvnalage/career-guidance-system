function CollapsibleCard({
    sectionKey,
    title,
    eyebrow,
    children,
    collapsedSections,
    toggleSection,
    actions = null,
    contentId,
    className = "card",
}) {
    const isCollapsed = collapsedSections[sectionKey];

    return (
        <article className={className}>
            <div className="collapsible-card-header">
                <button
                    type="button"
                    className="collapsible-trigger"
                    aria-expanded={!isCollapsed}
                    aria-controls={contentId}
                    onClick={() => toggleSection(sectionKey)}
                >
                    <div>
                        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
                        <h2>{title}</h2>
                    </div>
                    <span className="collapse-icon" aria-hidden="true">
                        {isCollapsed ? "Expand" : "Minimize"}
                    </span>
                </button>
                {actions}
            </div>
            {!isCollapsed ? (
                <div id={contentId} className="collapsible-content">
                    {children}
                </div>
            ) : null}
        </article>
    );
}

function DashboardHero({
    summary,
    topRolesText,
    nextAction,
    profileSignals,
    conversationTurns,
    recommendationRuns,
    collapsedSections,
    toggleSection,
}) {
    return (
        <CollapsibleCard
            sectionKey="hero"
            eyebrow="Career Command Center"
            title="Your career snapshot"
            collapsedSections={collapsedSections}
            toggleSection={toggleSection}
            contentId="dashboard-hero-content"
            className="card dashboard-hero"
        >
            <div className="dashboard-collapsible-grid">
                <div>
                    <p className="muted-text dashboard-hero-copy">
                        Track progress quickly, then jump to the next action.
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
                        <span>Top Career Signals</span>
                        <strong>{topRolesText}</strong>
                    </div>
                    <div className="metric-item">
                        <span>Priority Next Step</span>
                        <strong>{nextAction}</strong>
                    </div>
                </div>
            </div>
        </CollapsibleCard>
    );
}

export { DashboardHero };
export default CollapsibleCard;
