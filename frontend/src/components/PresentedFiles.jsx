import {
  ArchiveBoxIcon,
  ArrowDownTrayIcon,
  DocumentIcon,
} from "@heroicons/react/24/outline";
import "./PresentedFiles.css";

const API_BASE = "http://localhost:8000";

export default function PresentedFiles({ files }) {
  if (!files || files.length === 0) return null;

  return (
    <div className="presented-files">
      <h4 className="presented-files-title">
        <ArchiveBoxIcon className="heroicon" aria-hidden="true" />
        <span>Презентованные файлы</span>
      </h4>
      <div className="presented-files-grid">
        {files.map((file, i) => (
          <div key={i} className="presented-file-card">
            <div className="presented-file-name" title={file.path}>
              <DocumentIcon className="heroicon" aria-hidden="true" />
              <span>{file.name}</span>
            </div>
            <button
              className="presented-file-download"
              onClick={() => {
                const url = `${API_BASE}/sandbox/download?path=${encodeURIComponent(file.path)}`;
                window.open(url, "_blank");
              }}
            >
              <ArrowDownTrayIcon className="heroicon" aria-hidden="true" />
              <span>Скачать</span>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
