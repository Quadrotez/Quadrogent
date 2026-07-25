import { useState } from "react";
import "./SettingsModal.css";
import "./ProfilePanel.css";

export default function ProfilePanel({
  userName,
  setUserName,
  userInfo,
  setUserInfo,
  systemPrompt,
  setSystemPrompt,
  modelSettings,
  setModelSettings,
  saving,
  error,
  savedMsg,
  onSave,
  onClose,
}) {
  const [activeTab, setActiveTab] = useState("profile");

  const handleModelSettingChange = (key, value) => {
    setModelSettings((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal profile-modal" onClick={(e) => e.stopPropagation()}>
        <h2>Профиль</h2>

        <div className="profile-tabs">
          <button
            type="button"
            className={`tab-button ${activeTab === "profile" ? "active" : ""}`}
            onClick={() => setActiveTab("profile")}
          >
            Профиль
          </button>
          <button
            type="button"
            className={`tab-button ${activeTab === "prompt" ? "active" : ""}`}
            onClick={() => setActiveTab("prompt")}
          >
            Системный промпт
          </button>
          <button
            type="button"
            className={`tab-button ${activeTab === "llm" ? "active" : ""}`}
            onClick={() => setActiveTab("llm")}
          >
            Параметры LLM
          </button>
        </div>

        <div className="settings-content">
          {activeTab === "profile" && (
            <div className="settings-section">
              <div className="setting-group">
                <label>Имя</label>
                <input
                  type="text"
                  className="settings-input"
                  value={userName}
                  onChange={(e) => setUserName(e.target.value)}
                  placeholder="Как к вам обращаться"
                />
                <span className="setting-info">
                  Имя будет учитываться в системном промпте.
                </span>
              </div>

              <div className="setting-group">
                <label>Информация о вас</label>
                <textarea
                  className="settings-textarea"
                  value={userInfo}
                  onChange={(e) => setUserInfo(e.target.value)}
                  placeholder="Расскажите о себе: чем занимаетесь, какие технологии используете, что интересно..."
                  rows={5}
                />
                <span className="setting-info">
                  Необязательно. Помогает ИИ лучше понимать контекст ваших запросов.
                </span>
              </div>
            </div>
          )}

          {activeTab === "prompt" && (
            <div className="settings-section">
              <div className="setting-group">
                <label>Системный промпт</label>
                <textarea
                  className="settings-textarea settings-textarea--tall"
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="Введите системный промпт..."
                  rows={14}
                />
                <span className="setting-info">
                  Базовая инструкция для модели. Если пусто — используется промпт по умолчанию.
                </span>
              </div>
            </div>
          )}

          {activeTab === "llm" && (
            <div className="settings-section">
              <p className="settings-hint">
                Параметры применяются ко всем запросам (Ollama и облачные провайдеры).
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

              <div className="setting-group setting-toggle-group">
                <label className="setting-toggle-label">
                  <span>
                    <span className="setting-toggle-title">Генерация заголовков</span>
                    <span className="setting-info">
                      ИИ создаёт короткий заголовок для нового чата (до 30 символов).
                    </span>
                  </span>
                  <button
                    type="button"
                    className={`setting-toggle ${modelSettings.generate_titles === "true" ? "setting-toggle--on" : ""}`}
                    onClick={() =>
                      handleModelSettingChange(
                        "generate_titles",
                        modelSettings.generate_titles === "true" ? "false" : "true"
                      )
                    }
                  >
                    <span className="setting-toggle-knob" />
                  </button>
                </label>
              </div>
            </div>
          )}
        </div>

        {error && <div className="settings-error">{error}</div>}
        {savedMsg && <div className="settings-success">{savedMsg}</div>}

        <div className="settings-actions">
          <button
            type="button"
            className="send-button"
            onClick={onSave}
            disabled={saving}
          >
            {saving ? "Сохранение..." : "Сохранить"}
          </button>
          <button type="button" className="settings-close" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
