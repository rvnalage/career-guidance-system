import { useEffect, useState } from "react";

import { RagSearchPanel, RuntimeSignalsPanel } from "../components/Dashboard/CareerOptions";
import { apiClient } from "../services/api";

const defaultConfig = {
    enabled: true,
    provider: "ollama",
    base_url: "http://localhost:11434",
    model: "tinyllama:latest",
    request_timeout_seconds: 60,
    ollama_num_predict: 96,
    chat_reply_max_sentences: 8,
    require_rag_context: true,
    auto_fallback_to_openai: false,
    openai_base_url: "https://api.openai.com/v1",
    openai_model: "gpt-4o-mini",
    openai_max_tokens: 260,
    groq_model: "llama-3.1-8b-instant",
    groq_max_tokens: 512,
};

function SettingsPage() {
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [status, setStatus] = useState("");
    const [config, setConfig] = useState(defaultConfig);
    const [runtimeStatus, setRuntimeStatus] = useState(null);
    const [ragStatus, setRagStatus] = useState(null);
    const [xaiStatus, setXaiStatus] = useState(null);
    const [ragQuery, setRagQuery] = useState("career roadmap");
    const [ragResults, setRagResults] = useState([]);
    const [ragBusy, setRagBusy] = useState(false);

    const hydrateFromStatus = (data) => {
        setRuntimeStatus(data);
        setConfig({
            enabled: Boolean(data.enabled),
            provider: data.provider || "ollama",
            base_url: data.base_url || defaultConfig.base_url,
            model: data.base_model || defaultConfig.model,
            request_timeout_seconds: Number(data.request_timeout_seconds || defaultConfig.request_timeout_seconds),
            ollama_num_predict: Number(data.ollama_num_predict || defaultConfig.ollama_num_predict),
            chat_reply_max_sentences: Number(data.chat_reply_max_sentences || defaultConfig.chat_reply_max_sentences),
            require_rag_context: Boolean(data.require_rag_context),
            auto_fallback_to_openai: Boolean(data.auto_fallback_to_openai),
            openai_base_url: data.openai_base_url || defaultConfig.openai_base_url,
            openai_model: data.openai_model || defaultConfig.openai_model,
            openai_max_tokens: Number(data.openai_max_tokens || defaultConfig.openai_max_tokens),
            groq_model: data.groq_model || defaultConfig.groq_model,
            groq_max_tokens: Number(data.groq_max_tokens || defaultConfig.groq_max_tokens),
        });
    };

    const loadStatus = async () => {
        setLoading(true);
        try {
            const response = await apiClient.get("/llm/status");
            hydrateFromStatus(response.data || {});
            setStatus("");
        } catch (err) {
            setStatus(err.response?.data?.detail || "Failed to load LLM runtime settings.");
        } finally {
            setLoading(false);
        }
    };

    const loadRagStatus = async () => {
        try {
            const response = await apiClient.get("/rag/status");
            setRagStatus(response.data);
        } catch (err) {
            setStatus(err.response?.data?.detail || "Failed to load RAG status.");
        }
    };

    useEffect(() => {
        loadStatus();
        loadRagStatus();
        loadXaiStatus();
    }, []);

    const loadXaiStatus = async () => {
        try {
            const response = await apiClient.get("/recommendations/xai/status");
            setXaiStatus(response.data);
        } catch {
            setXaiStatus(null);
        }
    };

    const updateField = (field, value) => {
        setConfig((prev) => ({ ...prev, [field]: value }));
    };

    const onSave = async (event) => {
        event.preventDefault();
        setSaving(true);
        try {
            const payload = {
                enabled: config.enabled,
                provider: config.provider,
                base_url: config.base_url,
                model: config.model,
                request_timeout_seconds: Number(config.request_timeout_seconds) || 60,
                ollama_num_predict: Number(config.ollama_num_predict) || 96,
                chat_reply_max_sentences: Number(config.chat_reply_max_sentences) || 8,
                require_rag_context: config.require_rag_context,
                auto_fallback_to_openai: config.auto_fallback_to_openai,
                openai_base_url: config.openai_base_url,
                openai_model: config.openai_model,
                openai_max_tokens: Number(config.openai_max_tokens) || defaultConfig.openai_max_tokens,
                groq_model: config.groq_model,
                groq_max_tokens: Number(config.groq_max_tokens) || defaultConfig.groq_max_tokens,
            };
            const response = await apiClient.post("/llm/config", payload);
            hydrateFromStatus(response.data || {});
            setStatus("Runtime LLM settings saved.");
        } catch (err) {
            setStatus(err.response?.data?.detail || "Failed to save runtime LLM settings.");
        } finally {
            setSaving(false);
        }
    };

    const onReset = async () => {
        setSaving(true);
        try {
            const response = await apiClient.post("/llm/config/reset");
            hydrateFromStatus(response.data || {});
            setStatus("Runtime overrides cleared. Environment defaults restored.");
        } catch (err) {
            setStatus(err.response?.data?.detail || "Failed to reset runtime overrides.");
        } finally {
            setSaving(false);
        }
    };

    const ingestDefaultRag = async () => {
        setRagBusy(true);
        try {
            await apiClient.post("/rag/ingest/default");
            await loadRagStatus();
            setStatus("RAG knowledge ingestion completed.");
        } catch (err) {
            setStatus(err.response?.data?.detail || "Failed to ingest default RAG documents.");
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
            setStatus(err.response?.data?.detail || "Failed to search RAG knowledge.");
        } finally {
            setRagBusy(false);
        }
    };

    return (
        <section className="card settings-layout">
            <div className="settings-header">
                <h2 className="page-heading-row"><span className="page-heading-symbol" aria-hidden="true">⚙️</span>Settings</h2>
                <p className="muted-text">Manage runtime model controls and retrieval (RAG) knowledge operations.</p>
            </div>

            {loading ? <p className="muted-text">Loading runtime configuration...</p> : null}
            {status ? <p className="status-inline">{status}</p> : null}

            <div className="settings-meta card">
                <h3>Runtime Signals</h3>
                <p className="muted-text">Operational snapshot of current LLM, XAI and RAG state.</p>
                <RuntimeSignalsPanel llmStatus={runtimeStatus} xaiStatus={xaiStatus} ragStatus={ragStatus} />
            </div>

            <form className="settings-form" onSubmit={onSave}>
                <label className="settings-check">
                    <input
                        type="checkbox"
                        checked={config.enabled}
                        onChange={(event) => updateField("enabled", event.target.checked)}
                    />
                    <span>Enable LLM refinement</span>
                </label>

                <label>
                    Provider
                    <select value={config.provider} onChange={(event) => updateField("provider", event.target.value)}>
                        <option value="ollama">ollama (local)</option>
                        <option value="groq">groq (cloud, fast)</option>
                        <option value="openai">openai (cloud)</option>
                    </select>
                </label>

                {/* Ollama-specific fields */}
                {config.provider === "ollama" && (
                    <>
                        <label>
                            Ollama Base URL
                            <input
                                value={config.base_url}
                                onChange={(event) => updateField("base_url", event.target.value)}
                                placeholder="http://localhost:11434"
                            />
                        </label>
                        <label>
                            Ollama Model
                            <input
                                value={config.model}
                                onChange={(event) => updateField("model", event.target.value)}
                                placeholder="tinyllama:latest"
                            />
                        </label>
                        <label>
                            Ollama Max Predict Tokens
                            <input
                                type="number"
                                min="24"
                                max="256"
                                value={config.ollama_num_predict}
                                onChange={(event) => updateField("ollama_num_predict", event.target.value)}
                            />
                        </label>
                    </>
                )}

                {/* Groq-specific fields */}
                {config.provider === "groq" && (
                    <>
                        <label>
                            Groq Model
                            <input
                                value={config.groq_model}
                                onChange={(event) => updateField("groq_model", event.target.value)}
                                placeholder="llama-3.1-8b-instant"
                            />
                        </label>
                        <label>
                            Groq Max Tokens
                            <input
                                type="number"
                                min="64"
                                max="4096"
                                value={config.groq_max_tokens}
                                onChange={(event) => updateField("groq_max_tokens", event.target.value)}
                            />
                        </label>
                        <div className="settings-effective-model">
                            <span className="settings-effective-label">GROQ_API_KEY</span>
                            <strong className="settings-effective-value">
                                {runtimeStatus?.groq_api_key_configured ? "✓ configured" : "✗ missing — set GROQ_API_KEY env var"}
                            </strong>
                        </div>
                    </>
                )}

                {/* OpenAI-specific fields */}
                {config.provider === "openai" && (
                    <>
                        <label>
                            OpenAI Base URL
                            <input
                                value={config.openai_base_url}
                                onChange={(event) => updateField("openai_base_url", event.target.value)}
                                placeholder="https://api.openai.com/v1"
                            />
                        </label>
                        <label>
                            OpenAI Model
                            <input
                                value={config.openai_model}
                                onChange={(event) => updateField("openai_model", event.target.value)}
                                placeholder="gpt-4o-mini"
                            />
                        </label>
                        <label>
                            OpenAI Max Tokens
                            <input
                                type="number"
                                min="64"
                                max="2048"
                                value={config.openai_max_tokens}
                                onChange={(event) => updateField("openai_max_tokens", event.target.value)}
                            />
                        </label>
                        <div className="settings-effective-model">
                            <span className="settings-effective-label">OPENAI_API_KEY</span>
                            <strong className="settings-effective-value">
                                {runtimeStatus?.openai_api_key_configured ? "✓ configured" : "✗ missing — set OPENAI_API_KEY env var"}
                            </strong>
                        </div>
                    </>
                )}

                {runtimeStatus ? (
                    <div className="settings-effective-model">
                        <span className="settings-effective-label">Effective Active Model</span>
                        <strong className="settings-effective-value">
                            {runtimeStatus.active_model || runtimeStatus.base_model || "--"}
                        </strong>
                        {runtimeStatus.is_finetuned_active ? (
                            <span className="settings-finetuned-badge">finetuned</span>
                        ) : null}
                    </div>
                ) : null}

                <label>
                    Request Timeout (seconds)
                    <input
                        type="number"
                        min="5"
                        max="300"
                        value={config.request_timeout_seconds}
                        onChange={(event) => updateField("request_timeout_seconds", event.target.value)}
                    />
                </label>

                <label>
                    Reply Sentence Cap
                    <input
                        type="number"
                        min="1"
                        max="20"
                        value={config.chat_reply_max_sentences}
                        onChange={(event) => updateField("chat_reply_max_sentences", event.target.value)}
                    />
                </label>

                <label className="settings-check">
                    <input
                        type="checkbox"
                        checked={config.require_rag_context}
                        onChange={(event) => updateField("require_rag_context", event.target.checked)}
                    />
                    <span>Require RAG context before LLM call</span>
                </label>

                {config.provider === "ollama" && (
                    <fieldset className="settings-fallback">
                        <legend>Fallback from local to cloud</legend>
                        <label className="settings-check">
                            <input
                                type="checkbox"
                                checked={config.auto_fallback_to_openai}
                                onChange={(event) => updateField("auto_fallback_to_openai", event.target.checked)}
                            />
                            <span>When ollama fails, retry with OpenAI-compatible endpoint</span>
                        </label>

                        <label>
                            Fallback Cloud Base URL
                            <input
                                value={config.openai_base_url}
                                onChange={(event) => updateField("openai_base_url", event.target.value)}
                                placeholder="https://api.openai.com/v1"
                            />
                        </label>

                        <label>
                            Fallback Cloud Model
                            <input
                                value={config.openai_model}
                                onChange={(event) => updateField("openai_model", event.target.value)}
                                placeholder="gpt-4o-mini"
                            />
                        </label>
                    </fieldset>
                )}

                <div className="settings-actions">
                    <button className="button" type="submit" disabled={saving || loading}>
                        {saving ? "Saving..." : "Save Runtime Settings"}
                    </button>
                    <button className="button ghost" type="button" disabled={saving || loading} onClick={onReset}>
                        Reset Overrides
                    </button>
                </div>
            </form>

            <div className="settings-meta card">
                <div className="collapsible-card-header">
                    <h3>RAG Admin Tools</h3>
                    <button className="button secondary" type="button" onClick={ingestDefaultRag} disabled={ragBusy}>
                        {ragBusy ? "Processing..." : "Ingest Default Docs"}
                    </button>
                </div>
                <p className="muted-text">Chunk status: {ragStatus?.total_chunks ?? "--"} | Sources: {ragStatus?.total_sources ?? "--"}</p>
                <RagSearchPanel
                    ragQuery={ragQuery}
                    setRagQuery={setRagQuery}
                    searchRag={searchRag}
                    ragBusy={ragBusy}
                    ragResults={ragResults}
                />
            </div>

            <div className="settings-meta card">
                <h3>Runtime Diagnostics</h3>
                <p className="muted-text">Configured cloud API key status is read from backend environment, not editable here.</p>
                <div className="metric-grid">
                    <div className="metric-item"><span>Provider</span>{runtimeStatus?.provider || "-"}</div>
                    <div className="metric-item"><span>Active model</span>{runtimeStatus?.active_model || "-"}</div>
                    <div className="metric-item"><span>Request timeout</span>{runtimeStatus?.request_timeout_seconds ?? "-"}</div>
                    <div className="metric-item"><span>Ollama max predict</span>{runtimeStatus?.ollama_num_predict ?? "-"}</div>
                    <div className="metric-item"><span>Sentence cap</span>{runtimeStatus?.chat_reply_max_sentences ?? "-"}</div>
                    {runtimeStatus?.provider === "openai" && <div className="metric-item"><span>OpenAI max tokens</span>{runtimeStatus?.openai_max_tokens ?? "-"}</div>}
                    {runtimeStatus?.provider === "groq" && <div className="metric-item"><span>Groq max tokens</span>{runtimeStatus?.groq_max_tokens ?? "-"}</div>}
                    <div className="metric-item"><span>Runtime override</span>{runtimeStatus?.runtime_override_active ? "active" : "env default"}</div>
                    <div className="metric-item"><span>OPENAI_API_KEY</span>{runtimeStatus?.openai_api_key_configured ? "configured" : "missing"}</div>
                    <div className="metric-item"><span>GROQ_API_KEY</span>{runtimeStatus?.groq_api_key_configured ? "configured" : "missing"}</div>
                    {runtimeStatus?.provider === "groq" && <div className="metric-item"><span>Groq model</span>{runtimeStatus?.groq_model || "-"}</div>}
                </div>
            </div>
        </section >
    );
}

export default SettingsPage;
