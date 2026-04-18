import { useEffect, useState } from "react";

import ConfirmModal from "../components/Common/ConfirmModal";
import { apiClient } from "../services/api";

const DEFAULT_PSYCHOMETRIC = {
    investigative: 3,
    realistic: 3,
    artistic: 3,
    social: 3,
    enterprising: 3,
    conventional: 3,
};

function ProfilePage({ isAuthenticated, currentUser }) {
    const [form, setForm] = useState({
        interests: "",
        skills: "",
        education_level: "master",
    });
    const [psychometric, setPsychometric] = useState(DEFAULT_PSYCHOMETRIC);
    const [psychometricResult, setPsychometricResult] = useState(null);
    const [uploadFiles, setUploadFiles] = useState([]);
    const [uploadMessage, setUploadMessage] = useState("");
    const [uploadBusy, setUploadBusy] = useState(false);
    const [loading, setLoading] = useState(false);
    const [saveBusy, setSaveBusy] = useState(false);
    const [saveMessage, setSaveMessage] = useState("");
    const [error, setError] = useState("");
    const [pendingPsychometricDelete, setPendingPsychometricDelete] = useState(false);
    const [pendingResetAllData, setPendingResetAllData] = useState(false);

    const skillsCount = form.skills.split(",").map((item) => item.trim()).filter(Boolean).length;
    const interestsCount = form.interests.split(",").map((item) => item.trim()).filter(Boolean).length;
    const profileCompletion = Math.round(([
        form.education_level ? 1 : 0,
        skillsCount > 0 ? 1 : 0,
        interestsCount > 0 ? 1 : 0,
        psychometricResult ? 1 : 0,
    ].reduce((acc, value) => acc + value, 0) / 4) * 100);
    const completionChecks = [
        { label: "Education level selected", done: Boolean(form.education_level) },
        { label: "Skills added", done: skillsCount > 0 },
        { label: "Interests added", done: interestsCount > 0 },
        { label: "Psychometric completed", done: Boolean(psychometricResult) },
    ];
    const profileHighlights = [
        skillsCount === 0 ? "Add at least 5 core skills" : `${skillsCount} skills captured`,
        interestsCount === 0 ? "Add 2-3 career interests" : `${interestsCount} interests captured`,
        psychometricResult ? `Top domains: ${psychometricResult.recommended_domains?.slice(0, 2).join(", ") || "Ready"}` : "Complete psychometric assessment",
    ];

    // Load profiles on mount
    useEffect(() => {
        if (isAuthenticated) {
            loadPsychometricProfile();
            loadCareerProfile();
        }
    }, [isAuthenticated]);

    const loadCareerProfile = async () => {
        try {
            const response = await apiClient.get("/profile-intake/me");
            const data = response.data || {};
            setForm((prev) => ({
                ...prev,
                skills: (data.skills || []).join(", "),
                interests: (data.interests || []).join(", "),
                education_level: data.education_level || prev.education_level,
            }));
        } catch (err) {
            if (err.response?.status !== 401 && err.response?.status !== 404) {
                setError(err.response?.data?.detail || "Could not load saved profile");
            }
        }
    };

    const saveCareerProfile = async () => {
        setSaveBusy(true);
        setSaveMessage("");
        setError("");
        try {
            await apiClient.put("/profile-intake/me", {
                skills: form.skills.split(",").map((s) => s.trim()).filter(Boolean),
                interests: form.interests.split(",").map((s) => s.trim()).filter(Boolean),
                education_level: form.education_level || null,
                target_role: null,
                psychometric_dimensions: {},
            });
            setSaveMessage("Profile saved successfully.");
        } catch (err) {
            setError(err.response?.data?.detail || "Could not save profile");
        } finally {
            setSaveBusy(false);
        }
    };

    const loadPsychometricProfile = async () => {
        try {
            const response = await apiClient.get("/psychometric/profile/me");
            const data = response.data;
            if (data && Object.keys(data.normalized_scores || {}).length > 0) {
                setPsychometricResult(data);
            } else {
                setPsychometricResult(null);
            }
        } catch (err) {
            if (err.response?.status !== 401) {
                setError(err.response?.data?.detail || "Could not load psychometric profile");
            }
        }
    };

    const uploadProfileFiles = async () => {
        if (uploadFiles.length === 0) {
            return;
        }

        setUploadBusy(true);
        setUploadMessage("");
        setError("");
        try {
            const formData = new FormData();
            formData.append("owner_type", "self");
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

            setUploadMessage(response.data?.message || "Upload parsed successfully.");
            setUploadFiles([]);
        } catch (err) {
            setUploadMessage(err.response?.data?.detail || "Could not parse uploaded files");
        } finally {
            setUploadBusy(false);
        }
    };

    const scorePsychometric = async () => {
        setError("");
        try {
            const response = await apiClient.post("/psychometric/score/me", {
                dimensions: psychometric,
            });
            setPsychometricResult(response.data);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not score psychometric profile");
        }
    };

    const deletePsychometricProfile = async () => {
        setError("");
        try {
            await apiClient.delete("/psychometric/profile/me");
            setPsychometricResult(null);
            setPendingPsychometricDelete(false);
        } catch (err) {
            setError(err.response?.data?.detail || "Could not delete psychometric profile");
        }
    };

    const resetAllData = async () => {
        setError("");
        setLoading(true);
        try {
            await apiClient.delete("/user/data/me");
            // Reset local state
            setForm({
                interests: "",
                skills: "",
                education_level: "master",
            });
            setPsychometric(DEFAULT_PSYCHOMETRIC);
            setPsychometricResult(null);
            setUploadFiles([]);
            setUploadMessage("All your data has been reset successfully.");
            setPendingResetAllData(false);
        } catch (err) {
            if (err.response?.status === 404) {
                // Endpoint doesn't exist yet, show warning
                setError("Reset endpoint not yet implemented. Please contact support.");
            } else {
                setError(err.response?.data?.detail || "Could not reset data");
            }
        } finally {
            setLoading(false);
        }
    };

    if (!isAuthenticated) {
        return (
            <section className="card">
                <h2>My Profile</h2>
                <p className="muted-text">Please log in to access your profile.</p>
            </section>
        );
    }

    return (
        <section className="dashboard-stack">
            <section className="card">
                <h1>My Profile</h1>
                <p className="muted-text">Manage your career profile, skills, interests, and psychometric assessment.</p>
            </section>

            <section className="card profile-summary-card">
                <div className="collapsible-card-header">
                    <h2>📌 Profile Summary</h2>
                    <span className="dashboard-pill">{profileCompletion}% complete</span>
                </div>
                <div className="profile-summary-grid">
                    <article className="metric-item">
                        <span>Account</span>
                        <strong>{currentUser?.email || "--"}</strong>
                    </article>
                    <article className="metric-item">
                        <span>Education Level</span>
                        <strong>{form.education_level || "--"}</strong>
                    </article>
                    <article className="metric-item">
                        <span>Skills Captured</span>
                        <strong>{skillsCount}</strong>
                    </article>
                    <article className="metric-item">
                        <span>Interests Captured</span>
                        <strong>{interestsCount}</strong>
                    </article>
                    <article className="metric-item">
                        <span>Psychometric Status</span>
                        <strong>{psychometricResult ? "Completed" : "Pending"}</strong>
                    </article>
                    <article className="metric-item">
                        <span>Top Traits</span>
                        <strong>{psychometricResult?.top_traits?.slice(0, 2).join(", ") || "--"}</strong>
                    </article>
                </div>
                <div className="profile-summary-aux">
                    <article className="history-item">
                        <h4>Completion Checklist</h4>
                        <div className="profile-checklist">
                            {completionChecks.map((item) => (
                                <p key={item.label} className="profile-check-item">
                                    <span>{item.done ? "✓" : "○"}</span> {item.label}
                                </p>
                            ))}
                        </div>
                    </article>
                    <article className="history-item">
                        <h4>Profile Focus</h4>
                        <div className="profile-checklist">
                            {profileHighlights.map((item) => (
                                <p key={item} className="profile-check-item">• {item}</p>
                            ))}
                        </div>
                    </article>
                </div>
            </section>

            {error ? <div className="error-message">{error}</div> : null}
            {uploadMessage ? <div className="success-message">{uploadMessage}</div> : null}
            {saveMessage ? <div className="success-message">{saveMessage}</div> : null}

            {/* Resume & Profile Upload Section */}
            <section className="card">
                <div className="collapsible-card-header">
                    <h2>📄 Resume & Profile Upload</h2>
                </div>
                <div className="card-content">
                    <p className="muted-text">Upload your resume, CV, or profile documents. We'll extract your skills, interests, and education level.</p>
                    <div className="chat-upload-row">
                        <input
                            type="file"
                            multiple
                            accept=".txt,.md,.csv,.json,.log,.pdf"
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
                </div>
            </section>

            {/* Education, Skills & Interests Section */}
            <section className="card">
                <div className="collapsible-card-header">
                    <h2>🎓 Education, Skills &amp; Interests</h2>
                    <span className="muted-text" style={{ fontSize: "0.82rem" }}>Parsed from resume or enter manually — then Save</span>
                </div>
                <div className="card-content">
                    <label>
                        <span>Education Level</span>
                        <select value={form.education_level} onChange={(event) => setForm((prev) => ({ ...prev, education_level: event.target.value }))}>
                            <option value="high_school">High School</option>
                            <option value="diploma">Diploma</option>
                            <option value="bachelor">Bachelor</option>
                            <option value="master">Master</option>
                            <option value="phd">PhD</option>
                        </select>
                    </label>
                    <label style={{ marginTop: "0.8rem" }}>
                        <span>Skills</span>
                        <input
                            value={form.skills}
                            placeholder="Python, SQL, Machine Learning, Data Analysis"
                            onChange={(event) => setForm((prev) => ({ ...prev, skills: event.target.value }))}
                        />
                    </label>
                    <p className="muted-text" style={{ marginTop: "0.2rem", marginBottom: "0.6rem" }}>Comma-separated. Parsed automatically when you upload a resume above.</p>
                    <label>
                        <span>Interests</span>
                        <input
                            value={form.interests}
                            placeholder="Data Science, AI, Research, Blockchain"
                            onChange={(event) => setForm((prev) => ({ ...prev, interests: event.target.value }))}
                        />
                    </label>
                    <p className="muted-text" style={{ marginTop: "0.2rem", marginBottom: "1rem" }}>Comma-separated career interests for personalized recommendations.</p>
                    <button
                        className="button"
                        type="button"
                        onClick={saveCareerProfile}
                        disabled={saveBusy}
                    >
                        {saveBusy ? "Saving..." : "💾 Save Profile"}
                    </button>
                </div>
            </section>

            {/* Psychometric Assessment Section */}
            <section className="card">
                <div className="collapsible-card-header">
                    <h2>📊 Psychometric Assessment</h2>
                </div>
                <div className="card-content">
                    <p className="muted-text">Rate yourself on these six career dimensions (1-5 scale):</p>
                    <div className="psychometric-grid">
                        {Object.keys(psychometric).map((trait) => (
                            <label key={trait} className="slider-row">
                                <span className="trait-name">{trait}</span>
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
                    <div className="psych-action-row">
                        <button className="button" type="button" onClick={scorePsychometric}>
                            💾 Save My Psychometric Result
                        </button>
                        {psychometricResult ? (
                            <button
                                className="button secondary"
                                type="button"
                                onClick={() => setPendingPsychometricDelete(true)}
                            >
                                🗑 Delete Result
                            </button>
                        ) : null}
                    </div>

                    {psychometricResult ? (
                        <div className="psych-result-panel">
                            <div className="psych-result-section">
                                <h4 className="psych-result-heading">🎯 Top Traits</h4>
                                <div className="psych-trait-pills">
                                    {psychometricResult.top_traits.map((trait) => (
                                        <span key={trait} className="psych-trait-pill">{trait}</span>
                                    ))}
                                </div>
                            </div>
                            <div className="psych-result-section">
                                <h4 className="psych-result-heading">📈 Dimension Scores</h4>
                                <div className="psych-score-bars">
                                    {Object.entries(psychometricResult.normalized_scores).map(([dim, score]) => (
                                        <div key={dim} className="psych-score-row">
                                            <span className="psych-score-label">{dim}</span>
                                            <div className="psych-bar-track">
                                                <div
                                                    className="psych-bar-fill"
                                                    style={{ width: `${Math.round(score * 100)}%` }}
                                                />
                                            </div>
                                            <span className="psych-score-value">{(score * 100).toFixed(0)}%</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div className="psych-result-section">
                                <h4 className="psych-result-heading">💼 Recommended Career Domains</h4>
                                <div className="psych-domain-list">
                                    {psychometricResult.recommended_domains.map((domain, idx) => (
                                        <span key={domain} className="psych-domain-item">
                                            <span className="psych-domain-rank">{idx + 1}</span> {domain}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ) : null}
                </div>
            </section>

            {/* Data Management Section */}
            <section className="card">
                <div className="collapsible-card-header">
                    <h2>🗑️ Data Management</h2>
                </div>
                <div className="card-content">
                    <p className="muted-text">Manage your account data. Use the button below to reset all your profile data.</p>
                    <button
                        className="button secondary"
                        type="button"
                        onClick={() => setPendingResetAllData(true)}
                        disabled={loading}
                    >
                        {loading ? "Processing..." : "Reset All My Data"}
                    </button>
                </div>
            </section>

            <ConfirmModal
                open={pendingPsychometricDelete}
                title="Delete Psychometric Result"
                message="Are you sure you want to delete your psychometric assessment result? This action cannot be undone."
                confirmLabel="Delete"
                onConfirm={deletePsychometricProfile}
                onCancel={() => setPendingPsychometricDelete(false)}
            />

            <ConfirmModal
                open={pendingResetAllData}
                title="Reset All Data"
                message="This will permanently delete your resume, skills, interests, psychometric profile, recommendation history, and chat messages. This action cannot be undone. Are you sure?"
                confirmLabel="Reset Everything"
                onConfirm={resetAllData}
                onCancel={() => setPendingResetAllData(false)}
            />
        </section>
    );
}

export default ProfilePage;
