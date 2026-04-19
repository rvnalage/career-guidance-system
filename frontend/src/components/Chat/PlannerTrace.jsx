function PlannerTrace({
    steps = [],
    criticChanged = false,
    criticIssues = [],
    planId = null,
    planVariant = null,
    planVariantReason = null,
    plannerDurationMs = 0,
    outcomeScores = [],
    variant = "default",
}) {
    if (!steps.length && !criticChanged && !criticIssues.length && !planId && !planVariant && !plannerDurationMs && !outcomeScores.length) {
        return null;
    }

    const variantClass = variant === "panel" ? " trace-block-panel" : "";

    return (
        <div className={`trace-block${variantClass}`}>
            <p className="trace-heading">Agent Trace</p>
            {(planId || plannerDurationMs) ? (
                <div className="trace-run-meta">
                    {planId ? <span className="trace-run-chip">Run #{String(planId).slice(0, 8)}</span> : null}
                    {planVariant ? <span className="trace-run-chip">Variant {String(planVariant).split(":").at(-1)}</span> : null}
                    {plannerDurationMs > 0 ? <span className="trace-run-chip">Planner {plannerDurationMs} ms</span> : null}
                </div>
            ) : null}
            {planVariantReason ? <p className="trace-variant-reason">{planVariantReason}</p> : null}
            {outcomeScores.length ? (
                <div className="trace-outcome-row">
                    {outcomeScores.map((item, index) => (
                        <span key={`${item.intent || "intent"}-${index}`} className="trace-outcome-chip">
                            {String(item.intent || "intent").replaceAll("_", " ")}: {Number(item.score || 0)}
                        </span>
                    ))}
                </div>
            ) : null}
            {steps.length ? (
                <div className="trace-step-list">
                    {steps.map((step, index) => (
                        <div
                            key={`${step.name || "step"}-${index}`}
                            className={`trace-step-item${step.error_type ? " trace-step-item-error" : ""}`}
                        >
                            <div className="trace-step-head">
                                <span className="trace-step-name">{step.name?.replaceAll("_", " ") || "step"}</span>
                                <div className="trace-step-meta">
                                    {typeof step.duration_ms === "number" ? (
                                        <span className="trace-step-duration">{step.duration_ms} ms</span>
                                    ) : null}
                                    {step.error_type ? (
                                        <span className="trace-step-error-pill">{step.error_type}</span>
                                    ) : null}
                                </div>
                            </div>
                            <span className="trace-step-detail">{step.detail}</span>
                            {step.depends_on?.length ? (
                                <span className="trace-step-depends">
                                    depends on: {step.depends_on.map((item) => String(item).replaceAll("_", " ")).join(", ")}
                                </span>
                            ) : null}
                        </div>
                    ))}
                </div>
            ) : null}
            {criticChanged || criticIssues.length ? (
                <div className="critic-pill-row">
                    <span className={`critic-status-pill ${criticChanged ? "critic-updated" : "critic-clean"}`}>
                        {criticChanged ? "Verifier adjusted reply" : "Verifier passed"}
                    </span>
                    {criticIssues.map((issue, index) => (
                        <span key={`${issue}-${index}`} className="critic-issue-pill">{issue.replaceAll("_", " ")}</span>
                    ))}
                </div>
            ) : null}
        </div>
    );
}

export default PlannerTrace;