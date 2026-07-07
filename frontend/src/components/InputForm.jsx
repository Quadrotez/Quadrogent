import { useRef } from "react";
import "./InputForm.css";

export default function InputForm({
  input,
  setInput,
  isLoading,
  selectedModel,
  attachedFiles,
  setAttachedFiles,
  isDragging,
  setIsDragging,
  onSubmit,
  onStop,
}) {
  const textareaRef = useRef(null);

  const autoResize = (e) => {
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit(e);
    }
  };

  const handleFileAttach = (e) => {
    const files = Array.from(e.target.files);
    setAttachedFiles((prev) => [...prev, ...files]);
  };

  const handlePaste = (e) => {
    const items = e.clipboardData.items;
    const files = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].kind === "file") {
        files.push(items[i].getAsFile());
      }
    }
    if (files.length > 0) {
      setAttachedFiles((prev) => [...prev, ...files]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      setAttachedFiles((prev) => [...prev, ...files]);
    }
  };

  return (
    <form
      className={`input-form ${isDragging ? "dragging" : ""}`}
      onSubmit={onSubmit}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {attachedFiles.length > 0 && (
        <div className="attached-files-preview">
          {attachedFiles.map((file, i) => (
            <div key={i} className="attached-file-chip">
              📄 {file.name}
              <button
                type="button"
                className="attached-file-remove"
                onClick={() =>
                  setAttachedFiles((prev) => prev.filter((_, idx) => idx !== i))
                }
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="input-row">
        <label className="attach-button" title="Прикрепить файл">
          📎
          <input
            type="file"
            multiple
            onChange={handleFileAttach}
            style={{ display: "none" }}
          />
        </label>

        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            autoResize(e);
          }}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={
            isDragging
              ? "Отпустите файлы здесь"
              : selectedModel
              ? "Введите сообщение… (Shift+Enter — новая строка)"
              : "Загрузка моделей…"
          }
          className="message-input"
          rows={1}
          disabled={isLoading || !selectedModel}
        />

        {isLoading ? (
          <button type="button" onClick={onStop} className="stop-button">
            Стоп
          </button>
        ) : (
          <button
            type="submit"
            className="send-button"
            disabled={!selectedModel && attachedFiles.length === 0}
          >
            Отправить
          </button>
        )}
      </div>
    </form>
  );
}
