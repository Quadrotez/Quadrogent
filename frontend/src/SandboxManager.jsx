import { useState, useEffect } from "react";
import { fetchSandboxFiles, readSandboxFile, writeSandboxFile, clearSandbox, deleteSandboxFile } from "./api";
import "./SandboxManager.css";

const API_BASE = "http://localhost:8000";
const ROOT_PATH = "/home/quadrogent";

export default function SandboxManager({ onClose, mode = "modal", onToggleMode }) {
  const [currentPath, setCurrentPath] = useState(ROOT_PATH);
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Редактор файла
  const [editingFile, setEditingFile] = useState(null);
  const [editContent, setEditContent] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  const loadEntries = async (path) => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchSandboxFiles(path);
      setEntries(data.entries || []);
    } catch (e) {
      setError(e.message || "Ошибка загрузки");
      setEntries([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEntries(currentPath);
  }, [currentPath]);

  const navigateTo = (path) => {
    setEditingFile(null);
    setCurrentPath(path);
  };

  const navigateUp = () => {
    if (currentPath === ROOT_PATH || currentPath === "/") return;
    const parent = currentPath.split("/").slice(0, -1).join("/") || "/";
    navigateTo(parent);
  };

  const handleOpenFile = async (path) => {
    try {
      const data = await readSandboxFile(path);
      setEditingFile(path);
      setEditContent(data.content || "");
    } catch (e) {
      setError("Ошибка чтения файла: " + e.message);
    }
  };

  const handleSaveFile = async () => {
    setEditSaving(true);
    try {
      await writeSandboxFile(editingFile, editContent);
      setEditingFile(null);
      loadEntries(currentPath);
    } catch (e) {
      setError("Ошибка сохранения: " + e.message);
    } finally {
      setEditSaving(false);
    }
  };

  const handleDelete = async (entry) => {
    const label = entry.type === "dir" ? "папку" : "файл";
    if (!window.confirm(`Удалить ${label} «${entry.name}»?`)) return;
    try {
      await deleteSandboxFile(entry.path);
      loadEntries(currentPath);
    } catch (e) {
      setError("Ошибка удаления: " + e.message);
    }
  };

  const handleDownload = (entry) => {
    const url = `${API_BASE}/sandbox/download?path=${encodeURIComponent(entry.path)}`;
    window.open(url, "_blank");
  };

  const handleClear = async () => {
    if (!window.confirm("Очистить всё рабочее пространство модели?")) return;
    try {
      await clearSandbox();
      setCurrentPath(ROOT_PATH);
      loadEntries(ROOT_PATH);
    } catch (e) {
      setError("Ошибка очистки: " + e.message);
    }
  };

  // Хлебные крошки
  const buildBreadcrumbs = () => {
    const suffix = currentPath.startsWith(ROOT_PATH)
      ? currentPath.slice(ROOT_PATH.length)
      : currentPath;
    const parts = suffix.split("/").filter(Boolean);
    const crumbs = [{ label: "~", path: ROOT_PATH }];
    let acc = ROOT_PATH;
    for (const part of parts) {
      acc = acc + "/" + part;
      crumbs.push({ label: part, path: acc });
    }
    return crumbs;
  };

  const crumbs = buildBreadcrumbs();

  const isPanel = mode === "panel";

  const content = editingFile ? (
    /* Редактор файла */
    <div className="sandbox-editor">
      <div className="sandbox-editor-path">{editingFile}</div>
      <textarea
        className="sandbox-editor-textarea"
        value={editContent}
        onChange={(e) => setEditContent(e.target.value)}
        spellCheck={false}
      />
      <div className="sandbox-editor-actions">
        <button
          className="sandbox-btn sandbox-btn--primary"
          onClick={handleSaveFile}
          disabled={editSaving}
        >
          {editSaving ? "Сохранение…" : "Сохранить"}
        </button>
        <button className="sandbox-btn" onClick={() => setEditingFile(null)}>
          Отмена
        </button>
      </div>
    </div>
  ) : (
    /* Файловый браузер */
    <div className="sandbox-browser">
      {/* Хлебные крошки + кнопка назад */}
      <div className="sandbox-nav">
        <button
          className="sandbox-btn sandbox-btn--up"
          onClick={navigateUp}
          disabled={currentPath === ROOT_PATH}
          title="На уровень выше"
        >
          ⬆
        </button>
        <div className="sandbox-breadcrumbs">
          {crumbs.map((crumb, i) => (
            <span key={crumb.path} className="sandbox-breadcrumb">
              {i > 0 && <span className="sandbox-breadcrumb-sep">/</span>}
              <button
                className={`sandbox-breadcrumb-btn ${i === crumbs.length - 1 ? "active" : ""}`}
                onClick={() => navigateTo(crumb.path)}
                disabled={i === crumbs.length - 1}
              >
                {crumb.label}
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Ошибка */}
      {error && <div className="sandbox-error">{error}</div>}

      {/* Список файлов */}
      <div className="sandbox-file-list">
        {loading ? (
          <div className="sandbox-status">Загрузка…</div>
        ) : entries.length === 0 ? (
          <div className="sandbox-status sandbox-status--empty">Папка пуста</div>
        ) : (
          entries.map((entry) => (
            <div key={entry.path} className="sandbox-entry">
              <button
                className="sandbox-entry-name"
                onClick={() =>
                  entry.type === "dir"
                    ? navigateTo(entry.path)
                    : handleOpenFile(entry.path)
                }
                title={entry.path}
              >
                <span className="sandbox-entry-icon">
                  {entry.type === "dir" ? "📁" : "📄"}
                </span>
                <span className="sandbox-entry-label">{entry.name}</span>
              </button>

              <div className="sandbox-entry-actions">
                {entry.type === "file" && (
                  <button
                    className="sandbox-action-btn"
                    onClick={() => handleDownload(entry)}
                    title="Скачать"
                  >
                    ⬇
                  </button>
                )}
                <button
                  className="sandbox-action-btn sandbox-action-btn--delete"
                  onClick={() => handleDelete(entry)}
                  title="Удалить"
                >
                  🗑
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );

  if (isPanel) {
    return (
      <div className="sandbox-panel">
        <div className="sandbox-header">
          <h3 className="sandbox-title">📁 Файлы</h3>
          <div className="sandbox-header-actions">
            <button className="sandbox-btn sandbox-btn--danger" onClick={handleClear}>
              Очистить
            </button>
            <button
              className="sandbox-mode-toggle"
              onClick={onToggleMode}
              title="Открыть как модальное окно"
            >
              ⛶
            </button>
            <button className="sandbox-btn sandbox-btn--close" onClick={onClose} title="Закрыть панель">
              ✕
            </button>
          </div>
        </div>
        {content}
      </div>
    );
  }

  return (
    <div className="sandbox-overlay" onClick={onClose}>
      <div className="sandbox-modal" onClick={(e) => e.stopPropagation()}>
        {/* Заголовок */}
        <div className="sandbox-header">
          <h3 className="sandbox-title">📁 Файловая система модели</h3>
          <div className="sandbox-header-actions">
            <button className="sandbox-btn sandbox-btn--danger" onClick={handleClear}>
              Очистить всё
            </button>
            <button
              className="sandbox-mode-toggle"
              onClick={onToggleMode}
              title="Закрепить как панель справа"
            >
              ▤
            </button>
            <button className="sandbox-btn sandbox-btn--close" onClick={onClose} title="Закрыть">
              ✕
            </button>
          </div>
        </div>
        {content}
      </div>
    </div>
  );
}
