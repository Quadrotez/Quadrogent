import {
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  XCircleIcon,
} from "@heroicons/react/24/outline";
import { useState, useEffect } from "react";
import { fetchProviders, saveApiKey, testProvider } from "../api";
import "./ProviderManager.css";

export default function ProviderManager({ onSaved, onClose }) {
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [expandedProvider, setExpandedProvider] = useState(null);

  const [forms, setForms] = useState({});
  const [testResults, setTestResults] = useState({});
  const [testing, setTesting] = useState({});

  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    setLoading(true);
    try {
      const list = await fetchProviders();
      setProviders(list);
      const initialForms = {};
      for (const p of list) {
        initialForms[p.name] = {
          api_key: "",
          base_url: p.base_url || "",
          proxy_url: p.proxy_url || "",
        };
      }
      setForms(initialForms);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFormChange = (providerName, field, value) => {
    setForms((prev) => ({
      ...prev,
      [providerName]: { ...prev[providerName], [field]: value },
    }));
  };

  const handleToggleEnabled = async (providerName) => {
    const provider = providers.find((p) => p.name === providerName);
    const newEnabled = !provider.enabled;
    setSaving(true);
    try {
      await saveApiKey(providerName, undefined, undefined, undefined, newEnabled);
      await loadProviders();
      if (onSaved) onSaved();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async (providerName) => {
    setSaving(true);
    setError("");
    setSuccessMsg("");
    try {
      const form = forms[providerName];
      const provider = providers.find((p) => p.name === providerName);

      const apiKey = form.api_key.trim() || (provider.configured ? undefined : null);
      const baseUrl = form.base_url.trim() || provider.default_base_url || null;
      const proxyUrl = form.proxy_url.trim() || null;

      await saveApiKey(providerName, apiKey, baseUrl, proxyUrl);
      setSuccessMsg(`${provider.display_name} сохранён`);
      setTestResults((prev) => ({ ...prev, [providerName]: null }));
      await loadProviders();
      if (onSaved) onSaved();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (providerName) => {
    setTesting((prev) => ({ ...prev, [providerName]: true }));
    setTestResults((prev) => ({ ...prev, [providerName]: null }));
    try {
      const result = await testProvider(providerName);
      setTestResults((prev) => ({ ...prev, [providerName]: result }));
    } catch (e) {
      setTestResults((prev) => ({
        ...prev,
        [providerName]: { status: "error", message: e.message },
      }));
    } finally {
      setTesting((prev) => ({ ...prev, [providerName]: false }));
    }
  };

  const toggleExpand = (name) => {
    setExpandedProvider(expandedProvider === name ? null : name);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal pm-modal" onClick={(e) => e.stopPropagation()}>
        <h2>Провайдеры</h2>
        <p className="pm-subtitle">
          Настройте API-ключи и подключения к провайдерам моделей.
        </p>

        {loading && <div className="pm-loading">Загрузка...</div>}

        {!loading && (
          <div className="pm-list">
            {providers.map((p) => (
              <div
                key={p.name}
                className={`pm-provider ${expandedProvider === p.name ? "pm-provider--expanded" : ""}`}
              >
                <button
                  className="pm-provider-header"
                  onClick={() => toggleExpand(p.name)}
                >
                  <span className="pm-provider-dot" style={{ background: p.color }} />
                  <span className="pm-provider-name">{p.display_name}</span>
                  <span className={`pm-provider-status ${p.configured ? "pm-provider-status--ok" : ""} ${!p.enabled ? "pm-provider-status--off" : ""}`}>
                    {!p.enabled ? "Отключён" : p.configured ? "Настроен" : "Не настроен"}
                  </span>
                  <span
                    className={`pm-toggle ${p.enabled ? "pm-toggle--on" : ""}`}
                    onClick={(e) => { e.stopPropagation(); handleToggleEnabled(p.name); }}
                    title={p.enabled ? "Отключить" : "Включить"}
                  >
                    <span className="pm-toggle-thumb" />
                  </span>
                  <span className="pm-provider-arrow">
                    {expandedProvider === p.name ? (
                      <ChevronUpIcon className="heroicon" aria-hidden="true" />
                    ) : (
                      <ChevronDownIcon className="heroicon" aria-hidden="true" />
                    )}
                  </span>
                </button>

                {expandedProvider === p.name && (
                  <div className="pm-provider-body">
                    {p.needs_api_key && (
                      <div className="pm-field">
                        <label>API Key</label>
                        <input
                          type="password"
                          className="pm-input"
                          placeholder={p.configured ? "•••••••• (ключ сохранён)" : "Введите API ключ"}
                          value={forms[p.name]?.api_key || ""}
                          onChange={(e) => handleFormChange(p.name, "api_key", e.target.value)}
                        />
                      </div>
                    )}

                    <div className="pm-field">
                      <label>Base URL</label>
                      <input
                        type="text"
                        className="pm-input"
                        placeholder={p.default_base_url}
                        value={forms[p.name]?.base_url || ""}
                        onChange={(e) => handleFormChange(p.name, "base_url", e.target.value)}
                      />
                      <span className="pm-hint">
                        По умолчанию: {p.default_base_url}
                      </span>
                    </div>

                    <div className="pm-field">
                      <label>Proxy URL</label>
                      <input
                        type="text"
                        className="pm-input"
                        placeholder="socks5://host:port или http://host:port"
                        value={forms[p.name]?.proxy_url || ""}
                        onChange={(e) => handleFormChange(p.name, "proxy_url", e.target.value)}
                      />
                      <span className="pm-hint">Опционально. Поддерживается HTTP и SOCKS5.</span>
                    </div>

                    <div className="pm-buttons">
                      <button
                        className="pm-save-btn"
                        onClick={() => handleSave(p.name)}
                        disabled={saving}
                      >
                        {saving ? "Сохранение..." : "Сохранить"}
                      </button>
                      <button
                        className="pm-test-btn"
                        onClick={() => handleTest(p.name)}
                        disabled={testing[p.name]}
                      >
                        {testing[p.name] ? "Проверка..." : "Проверить"}
                      </button>
                    </div>

                    {testResults[p.name] && (
                      <div className={`pm-test-result pm-test-result--${testResults[p.name].status}`}>
                        {testResults[p.name].status === "ok" ? (
                          <CheckCircleIcon className="heroicon" aria-hidden="true" />
                        ) : (
                          <XCircleIcon className="heroicon" aria-hidden="true" />
                        )}
                        <span>{testResults[p.name].message}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {error && <div className="pm-error">{error}</div>}
        {successMsg && <div className="pm-success">{successMsg}</div>}

        <div className="pm-actions">
          <button className="pm-close-btn" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
