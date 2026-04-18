function ProfileContextPanel({
    uploadBusy,
    uploadFiles,
    setUploadFiles,
    uploadProfileFiles,
    uploadMessage,
    psychometric,
    setPsychometric,
    scorePsychometric,
    psychometricResult,
    onDeletePsychometric,
}) {
    return (
        <>
            <div className="chat-context-card" style={{ marginBottom: "0.75rem" }}>
                <p className="muted-text">For complete profile management, resume uploads, and data reset, visit the <strong>Profile</strong> tab. Below you can view and manage your psychometric assessment.</p>
            </div>
            <div className="psychometric-grid">
                {Object.keys(psychometric).map((trait) => (
                    <label key={trait} className="slider-row">
                        <span>{trait}</span>
                        <input
                            type="range"
                            min="1"
                            max="5"
                            value={psychometric[trait]}
                            onChange={(event) =>
                                setPsychometric((prev) => ({
                                    ...prev,
                                    [trait]: Number(event.target.value),
                                }))
                            }
                        />
                        <strong>{psychometric[trait]}</strong>
                    </label>
                ))}
            </div>
            <button className="button" type="button" onClick={scorePsychometric}>
                Score Psychometric Profile
            </button>
            {psychometricResult ? (
                <div className="history-list">
                    <article className="history-item">
                        <h4>Top Traits</h4>
                        <p>{psychometricResult.top_traits.join(", ")}</p>
                    </article>
                    <article className="history-item">
                        <h4>Recommended Domains</h4>
                        <p>{psychometricResult.recommended_domains.join(", ")}</p>
                    </article>
                    <button className="button secondary" type="button" onClick={onDeletePsychometric}>
                        Delete Psychometric Result
                    </button>
                </div>
            ) : null}
        </>
    );
}

export { ProfileContextPanel };
