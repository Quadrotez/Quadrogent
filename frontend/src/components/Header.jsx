import "./Header.css";

export default function Header({ models, selectedModel, isLoading, onModelChange, onOpenSandbox, onOpenSettings }) {
  return (
    <header className="header">
      <h1>Quadrogent</h1>
      <div className="header-controls">
        <div className="model-selector">
          <label htmlFor="model">Модель:</label>
          <select
            id="model"
            value={selectedModel}
            onChange={onModelChange}
            disabled={isLoading}
          >
            {models.length === 0 && <option value="">Нет доступных моделей</option>}
            {models.filter((m) => m.provider === "ollama").length > 0 && (
              <optgroup label="Ollama (локальные)">
                {models
                  .filter((m) => m.provider === "ollama")
                  .map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.name}
                    </option>
                  ))}
              </optgroup>
            )}
            {models.filter((m) => m.provider === "openrouter").length > 0 && (
              <optgroup label="OpenRouter">
                {models
                  .filter((m) => m.provider === "openrouter")
                  .map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.display_name || m.id}
                    </option>
                  ))}
              </optgroup>
            )}
          </select>
        </div>
        <button
          type="button"
          className="header-icon-btn"
          onClick={onOpenSandbox}
          title="Файлы песочницы"
        >
          📁
        </button>
        <button
          type="button"
          className="header-icon-btn"
          onClick={onOpenSettings}
          title="Настройки"
        >
          ⚙
        </button>
      </div>
    </header>
  );
}
