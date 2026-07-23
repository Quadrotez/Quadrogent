import { useState, useRef, useEffect } from "react";
import "./ModelSelector.css";

export default function ModelSelector({ models, selectedModel, isLoading, onSelect }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const panelRef = useRef(null);
  const searchRef = useRef(null);

  const ollamaModels = models.filter((m) => m.provider === "ollama");
  const openrouterModels = models.filter((m) => m.provider === "openrouter");

  const filter = (list) => {
    if (!search.trim()) return list;
    const q = search.toLowerCase();
    return list.filter(
      (m) =>
        (m.name && m.name.toLowerCase().includes(q)) ||
        (m.display_name && m.display_name.toLowerCase().includes(q)) ||
        (m.id && m.id.toLowerCase().includes(q))
    );
  };

  const filteredOllama = filter(ollamaModels);
  const filteredOpenrouter = filter(openrouterModels);

  const selectedDisplay = models.find((m) => m.name === selectedModel);
  const buttonText = selectedDisplay
    ? selectedDisplay.display_name || selectedDisplay.id || selectedDisplay.name
    : "Выберите модель";

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    const handleEscape = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  useEffect(() => {
    if (open && searchRef.current) {
      searchRef.current.focus();
    }
  }, [open]);

  const handleSelect = (name) => {
    onSelect(name);
    setOpen(false);
    setSearch("");
  };

  const renderModel = (m) => (
    <button
      key={m.name}
      className={`ms-model ${m.name === selectedModel ? "ms-model--active" : ""}`}
      onClick={() => handleSelect(m.name)}
    >
      <span className="ms-model-name">{m.display_name || m.id || m.name}</span>
      {m.name !== (m.display_name || m.id) && (
        <span className="ms-model-id">{m.name}</span>
      )}
    </button>
  );

  return (
    <div className="ms" ref={panelRef}>
      <button
        className="ms-trigger"
        onClick={() => setOpen(!open)}
        disabled={isLoading}
        title="Выбрать модель"
      >
        <span className="ms-trigger-label">{buttonText}</span>
        <span className="ms-trigger-arrow">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div className="ms-panel">
          <div className="ms-search-wrap">
            <input
              ref={searchRef}
              className="ms-search"
              type="text"
              placeholder="Поиск модели…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="ms-list">
            {filteredOllama.length > 0 && (
              <div className="ms-section">
                <div className="ms-section-header ms-section-header--ollama">
                  <span className="ms-section-dot ms-section-dot--ollama" />
                  Ollama
                  <span className="ms-section-count">{filteredOllama.length}</span>
                </div>
                {filteredOllama.map(renderModel)}
              </div>
            )}

            {filteredOpenrouter.length > 0 && (
              <div className="ms-section">
                <div className="ms-section-header ms-section-header--openrouter">
                  <span className="ms-section-dot ms-section-dot--openrouter" />
                  OpenRouter
                  <span className="ms-section-count">{filteredOpenrouter.length}</span>
                </div>
                {filteredOpenrouter.map(renderModel)}
              </div>
            )}

            {filteredOllama.length === 0 && filteredOpenrouter.length === 0 && (
              <div className="ms-empty">Ничего не найдено</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
