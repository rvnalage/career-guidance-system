import { useEffect, useState } from "react";

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
};

function SettingsPage() {
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [status, setStatus] = useState("");
    const [config, setConfig] = useState(defaultConfig);
    const [runtimeStatus, setRuntimeStatus] = useState(null);

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

    useEffect(() => {
        loadStatus();
    }, []);

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

    return (
        <section className="card settings-layout">
            <div className="settings-header">
                <h2>LLM Runtime Settings</h2>
                <p className="muted-text">Toggle between local TinyLlama and cloud provider without restarting backend.</p>
            </div>

            {loading ? <p className="muted-text">Loading runtime configuration...</p> : null}
            {status ? <p className="status-inline">{status}</p> : null}

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
                        <option value="openai">openai (cloud)</option>
                    </select>
                </label>

                <label>
                    Active Base URL
                    <input
                        value={config.base_url}
                        onChange={(event) => updateField("base_url", event.target.value)}
                        placeholder="http://localhost:11434 or https://api.openai.com/v1"
                    />
                </label>

                <label>
                    Active Model
                    <input
                        value={config.model}
                        onChange={(event) => updateField("model", event.target.value)}
                        placeholder="tinyllama:latest or gpt-4o-mini"
                    />
                </label>

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
                    Ollama Max Predict Tokens
                    <input
                        type="number"
                        min="24"
                        max="256"
                        value={config.ollama_num_predict}
                        onChange={(event) => updateField("ollama_num_predict", event.target.value)}
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
                <h3>Runtime Diagnostics</h3>
                <p className="muted-text">Configured cloud API key status is read from backend environment, not editable here.</p>
                <div className="metric-grid">
                    <div className="metric-item"><span>Provider</span>{runtimeStatus?.provider || "-"}</div>
                    <div className="metric-item"><span>Active model</span>{runtimeStatus?.active_model || "-"}</div>
                    <div className="metric-item"><span>Request timeout</span>{runtimeStatus?.request_timeout_seconds ?? "-"}</div>
                    <div className="metric-item"><span>Ollama max predict</span>{runtimeStatus?.ollama_num_predict ?? "-"}</div>
                    <div className="metric-item"><span>Sentence cap</span>{runtimeStatus?.chat_reply_max_sentences ?? "-"}</div>
                    <div className="metric-item"><span>Runtime override</span>{runtimeStatus?.runtime_override_active ? "active" : "env default"}</div>
                    <div className="metric-item"><span>OPENAI_API_KEY</span>{runtimeStatus?.openai_api_key_configured ? "configured" : "missing"}</div>
                </div>
            </div>
        </section>
    );
}

export default SettingsPage;
