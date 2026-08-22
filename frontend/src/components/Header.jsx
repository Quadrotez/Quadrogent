import { FolderIcon } from "@heroicons/react/24/outline";
import ModelSelector from "./ModelSelector";
import "./Header.css";

export default function Header({ models, selectedModel, isLoading, onModelSelect, onOpenProviders, sandboxOpen, sandboxMode, onOpenSandbox }) {
  return (
    <header className="header">
      <h1>Quadrogent</h1>
      <div className="header-controls">
        <ModelSelector
          models={models}
          selectedModel={selectedModel}
          isLoading={isLoading}
          onSelect={onModelSelect}
          onOpenProviders={onOpenProviders}
        />
        {!sandboxOpen && (
          <button
            type="button"
            className="header-icon-btn"
            onClick={onOpenSandbox}
            title="Файлы песочницы"
          >
            <FolderIcon className="heroicon" aria-hidden="true" />
          </button>
        )}
        {sandboxOpen && sandboxMode === "modal" && (
          <button
            type="button"
            className="header-icon-btn header-icon-btn--active"
            onClick={onOpenSandbox}
            title="Файлы открыты как модальное окно"
          >
            <FolderIcon className="heroicon" aria-hidden="true" />
          </button>
        )}
      </div>
    </header>
  );
}
