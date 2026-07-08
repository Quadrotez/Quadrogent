import { useState } from "react";
import "./SettingsModal.css";

export default function SettingsModal({
  openrouterConfigured,
  openrouterKeyInput,
  setOpenrouterKeyInput,
  modelSettings,
  setModelSettings,
  settingsSaving,
  settingsError,
  settingsSavedMsg,
  onSave,
  onClose,
}) {
  const [activeTab, setActiveTab] = useState("api");

  const handleModelSettingChange = (key, value) => {
    setModelSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Настройки</h2>
        
        <div className="settings-tabs">
          <button 
            className={`tab-button ${activeTab === "api" ? "active" : ""}`}
            onClick={() => setActiveTab("api")}
          >
            API Ключи
          </button>
          <button 
            className={`tab-button ${activeTab === "model" ? "active" : ""}`}
            onClick={() => setActiveTab("model")}
          >
            Настройки модели
          </button>
        </div>

        <div className="settings-content">
          {activeTab === "api" && (
            <div className="settings-section">
              <h3>OpenRouter</h3>
              <p className="settings-hint">
                {openrouterConfigured
                  ? "Ключ уже сохранён. Введите новый, чтобы заменить его."
                  : "Добавьте API-ключ, чтобы получить доступ к моделям OpenRouter."}
              </p>
              <input
                type="password"
                className="settings-input"
                placeholder="sk-or-v1-..."
                value={openrouterKeyInput}
                onChange={(e) => setOpenrouterKeyInput(e.target.value)}
              />
            </div>
          )}

          {activeTab === "model" && (
            <div className="settings-section">
              <h3>Параметры LLM</h3>
              <p className="settings-hint">
                Эти параметры будут применяться ко всем запросам (Ollama и OpenRouter).
              </p>
              
              <div className="setting-group">
                <label>Контекст (num_ctx)</label>
                <input
                  type="number"
                  className="settings-input"
                  value={modelSettings.model_num_ctx || ""}
                  onChange={(e) => handleModelSettingChange("model_num_ctx", e.target.value)}
                  placeholder="8192"
                />
                <span className="setting-info">Размер окна памяти (для Ollama).</span>
              </div>

              <div className="setting-group">
                <label>Температура</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  className="settings-input"
                  value={modelSettings.model_temperature || ""}
                  onChange={(e) => handleModelSettingChange("model_temperature", e.target.value)}
                  placeholder="0.0"
                />
                <span className="setting-info">Случайность ответа (0 — точный, 1 — креативный).</span>
              </div>

              <div className="setting-group">
                <label>Max Tokens</label>
                <input
                  type="number"
                  className="settings-input"
                  value={modelSettings.model_max_tokens || ""}
                  onChange={(e) => handleModelSettingChange("model_max_tokens", e.target.value)}
                  placeholder="4096"
                />
                <span className="setting-info">Максимальная длина одного ответа.</span>
              </div>

              <div className="setting-group">
                <label>Top P</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  className="settings-input"
                  value={modelSettings.model_top_p || ""}
                  onChange={(e) => handleModelSettingChange("model_top_p", e.target.value)}
                  placeholder="0.9"
                />
              </div>
            </div>
          )}
        </div>

        {settingsError && <div className="settings-error">{settingsError}</div>}
        {settingsSavedMsg && <div className="settings-success">{settingsSavedMsg}</div>}

        <div className="settings-actions">
          <button
            type="button"
            className="send-button"
            onClick={onSave}
            disabled={settingsSaving}
          >
            {settingsSaving ? "Сохранение..." : "Сохранить"}
          </button>
          <button type="button" className="settings-close" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
