import "./PresentedFiles.css";

const API_BASE = "http://localhost:8000";

export default function PresentedFiles({ files }) {
  if (!files || files.length === 0) return null;

  return (
    <div className="presented-files">
      <h4 className="presented-files-title">
        <span>🎁</span> Презентованные файлы
      </h4>
      <div className="presented-files-grid">
        {files.map((file, i) => (
          <div key={i} className="presented-file-card">
            <div className="presented-file-name" title={file.path}>
              📄 {file.name}
            </div>
            <button
              className="presented-file-download"
              onClick={() => {
                const url = `${API_BASE}/sandbox/download?path=${encodeURIComponent(file.path)}`;
                window.open(url, "_blank");
              }}
            >
              ⬇ Скачать
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
