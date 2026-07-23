import ModelSelector from "./ModelSelector";
import "./Header.css";

export default function Header({ models, selectedModel, isLoading, onModelSelect, sandboxOpen, sandboxMode, onOpenSandbox, onOpenSettings }) {
  return (
    <header className="header">
      <h1>Quadrogent</h1>
      <div className="header-controls">
        <ModelSelector
          models={models}
          selectedModel={selectedModel}
          isLoading={isLoading}
          onSelect={onModelSelect}
        />
        {!sandboxOpen && (
          <button
            type="button"
            className="header-icon-btn"
            onClick={onOpenSandbox}
            title="Файлы песочницы"
          >
            📁
          </button>
        )}
        {sandboxOpen && sandboxMode === "modal" && (
          <button
            type="button"
            className="header-icon-btn header-icon-btn--active"
            onClick={onOpenSandbox}
            title="Файлы открыты как модальное окно"
          >
            📁
          </button>
        )}
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
