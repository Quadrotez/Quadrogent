import "./SettingsModal.css";

export default function SettingsModal({
  openrouterConfigured,
  openrouterKeyInput,
  setOpenrouterKeyInput,
  settingsSaving,
  settingsError,
  settingsSavedMsg,
  onSave,
  onClose,
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Настройки</h2>
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
          <p className="settings-hint settings-hint--small">
            Ключ хранится в базе данных бэкенда (таблица api_keys) и никогда не передаётся
            третьим сторонам, кроме самого OpenRouter.
          </p>
        </div>
      </div>
    </div>
  );
}
