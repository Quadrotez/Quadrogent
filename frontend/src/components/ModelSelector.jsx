import { useState, useRef, useEffect } from "react";
import "./ModelSelector.css";

export default function ModelSelector({ models, selectedModel, isLoading, onSelect, onOpenProviders }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const panelRef = useRef(null);
  const searchRef = useRef(null);

  // Группируем модели по провайдеру динамически
  const grouped = {};
  for (const m of models) {
    const provider = m.provider || "unknown";
    if (!grouped[provider]) grouped[provider] = [];
    grouped[provider].push(m);
  }

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

  const filteredGrouped = {};
  for (const [provider, list] of Object.entries(grouped)) {
    const filtered = filter(list);
    if (filtered.length > 0) {
      filteredGrouped[provider] = filtered;
    }
  }

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

  const PROVIDER_COLORS = {
    ollama: "#4ade80",
    openrouter: "#a78bfa",
    groq: "#f97316",
  };

  const PROVIDER_LABELS = {
    ollama: "Ollama",
    openrouter: "OpenRouter",
    groq: "Groq",
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
            {Object.entries(filteredGrouped).map(([provider, list]) => (
              <div className="ms-section" key={provider}>
                <div className="ms-section-header">
                  <span
                    className="ms-section-dot"
                    style={{
                      background: PROVIDER_COLORS[provider] || "#888",
                      boxShadow: `0 0 6px ${PROVIDER_COLORS[provider] || "#888"}66`,
                    }}
                  />
                  {PROVIDER_LABELS[provider] || provider}
                  <span className="ms-section-count">{list.length}</span>
                </div>
                {list.map(renderModel)}
              </div>
            ))}

            {Object.keys(filteredGrouped).length === 0 && (
              <div className="ms-empty">Ничего не найдено</div>
            )}
          </div>

          <div className="ms-footer">
            <button
              className="ms-providers-btn"
              onClick={() => {
                setOpen(false);
                if (onOpenProviders) onOpenProviders();
              }}
            >
              Управление провайдерами
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
