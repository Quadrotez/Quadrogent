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
          <button
            type="button"
            className={`tab-button ${activeTab === "agent" ? "active" : ""}`}
            onClick={() => setActiveTab("agent")}
          >
            Агент
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

          {activeTab === "agent" && (
            <div className="settings-section">
              <p className="settings-hint">
                Настройки поведения AI-агента.
              </p>

              <div className="setting-group setting-toggle-group">
                <label className="setting-toggle-label">
                  <span>
                    <span className="setting-toggle-title">Несколько команд за раз</span>
                    <span className="setting-info">
                      Разрешить модели вызывать несколько инструментов за один ответ.
                    </span>
                  </span>
                  <button
                    type="button"
                    className={`setting-toggle ${modelSettings.multi_command !== "false" ? "setting-toggle--on" : ""}`}
                    onClick={() =>
                      handleModelSettingChange(
                        "multi_command",
                        modelSettings.multi_command === "false" ? "true" : "false"
                      )
                    }
                  >
                    <span className="setting-toggle-knob" />
                  </button>
                </label>
              </div>

              <div className="setting-group setting-toggle-group">
                <label className="setting-toggle-label">
                  <span>
                    <span className="setting-toggle-title">JSON-режим инструментов</span>
                    <span className="setting-info">
                      Для моделей без native tool calling (напр. qwen2.5-coder). Модель выводит JSON-блоки вместо API tool calls.
                    </span>
                  </span>
                  <button
                    type="button"
                    className={`setting-toggle ${modelSettings.tool_calling_mode === "json" ? "setting-toggle--on" : ""}`}
                    onClick={() =>
                      handleModelSettingChange(
                        "tool_calling_mode",
                        modelSettings.tool_calling_mode === "json" ? "native" : "json"
                      )
                    }
                  >
                    <span className="setting-toggle-knob" />
                  </button>
                </label>
              </div>

              <div className="setting-group setting-toggle-group">
                <label className="setting-toggle-label">
                  <span>
                    <span className="setting-toggle-title">Web Fetch</span>
                    <span className="setting-info">
                      Разрешить агенту загружать содержимое веб-страниц по URL.
                    </span>
                  </span>
                  <button
                    type="button"
                    className={`setting-toggle ${modelSettings.web_fetch_enabled !== "false" ? "setting-toggle--on" : ""}`}
                    onClick={() =>
                      handleModelSettingChange(
                        "web_fetch_enabled",
                        modelSettings.web_fetch_enabled === "false" ? "true" : "false"
                      )
                    }
                  >
                    <span className="setting-toggle-knob" />
                  </button>
                </label>
              </div>

              <div className="setting-group">
                <label>Провайдеры поиска</label>
                <div className="search-providers">
                  {[
                    { key: "duckduckgo", label: "DuckDuckGo" },
                    { key: "google", label: "Google" },
                    { key: "bing", label: "Bing" },
                    { key: "yandex", label: "Yandex" },
                  ].map((p) => {
                    const selected = (modelSettings.search_providers || "").split(",").map((s) => s.trim());
                    const checked = selected.includes(p.key);
                    return (
                      <label key={p.key} className="search-provider-checkbox">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            const current = (modelSettings.search_providers || "duckduckgo")
                              .split(",")
                              .map((s) => s.trim())
                              .filter(Boolean);
                            let next;
                            if (checked) {
                              next = current.filter((x) => x !== p.key);
                            } else {
                              next = [...current, p.key];
                            }
                            handleModelSettingChange("search_providers", next.join(","));
                          }}
                        />
                        <span>{p.label}</span>
                      </label>
                    );
                  })}
                </div>
                <span className="setting-info">
                  Какие поисковые системы использует инструмент web_search.
                </span>
              </div>

              <div className="setting-group">
                <label>Прокси для поиска</label>
                <input
                  type="text"
                  className="settings-input"
                  value={modelSettings.search_proxy || ""}
                  onChange={(e) => handleModelSettingChange("search_proxy", e.target.value)}
                  placeholder="socks5://user:pass@host:port"
                />
                <span className="setting-info">
                  Необязательно. Прокси для запросов web_search и web_fetch.
                </span>
              </div>

              <div className="setting-group">
                <label>Сохранённый контекст</label>
                <textarea
                  className="settings-textarea settings-textarea--tall"
                  value={modelSettings.self_context || ""}
                  onChange={(e) => handleModelSettingChange("self_context", e.target.value)}
                  placeholder="Контекст, который ИИ запоминает между разговорами..."
                  rows={8}
                />
                <span className="setting-info">
                  ИИ автоматически сохраняет сюда важную информацию через инструмент save_context.
                  Вы также можете редактировать или очищать этот контекст вручную.
                </span>
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
