function ProfileContextPanel({
    ownerType,
    setOwnerType,
    uploadBusy,
    uploadFiles,
    setUploadFiles,
    uploadProfileFiles,
    uploadMessage,
    psychometric,
    setPsychometric,
    scorePsychometric,
    psychometricResult,
}) {
    return (
        <>
            <div className="chat-context-card" style={{ marginBottom: "0.75rem" }}>
                <label>
                    Owner
                    <select value={ownerType} onChange={(event) => setOwnerType(event.target.value)}>
                        <option value="self">For myself</option>
                        <option value="on_behalf">On behalf of someone</option>
                    </select>
                </label>
                <div className="chat-upload-row">
                    <input
                        type="file"
                        multiple
                        accept=".txt,.md,.csv,.json,.log"
                        onChange={(event) => setUploadFiles(Array.from(event.target.files || []))}
                    />
                    <button
                        className="button secondary"
                        type="button"
                        onClick={uploadProfileFiles}
                        disabled={uploadBusy || uploadFiles.length === 0}
                    >
                        {uploadBusy ? "Parsing..." : "Parse Profile Files"}
                    </button>
                </div>
                {uploadMessage ? <p className="muted-text">{uploadMessage}</p> : null}
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
                </div>
            ) : null}
        </>
    );
}

export { ProfileContextPanel };
