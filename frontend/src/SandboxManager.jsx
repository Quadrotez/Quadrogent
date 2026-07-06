import React, { useState, useEffect } from 'react';
import { fetchSandboxFiles, readSandboxFile, writeSandboxFile, clearSandbox } from './api';

export default function SandboxManager({ onClose }) {
    const [files, setFiles] = useState("");
    const [currentPath, setCurrentPath] = useState("/home/quadrogent");
    const [loading, setLoading] = useState(false);
    const [editingFile, setEditingFile] = useState(null);
    const [editContent, setEditContent] = useState("");

    const loadFiles = async () => {
        setLoading(true);
        try {
            const data = await fetchSandboxFiles(currentPath);
            // Парсим вывод ls -R -F в массив объектов
            const lines = data.output.split('\n');
            const fileList = lines
                .filter(line => line.trim() && !line.includes(':') && !line.startsWith('total'))
                .map(line => {
                    const isDir = line.endsWith('/');
                    const name = isDir ? line.slice(0, -1) : line;
                    return {
                        name,
                        path: `${currentPath}/${name}`.replace(/\/+/g, '/'),
                        type: isDir ? 'dir' : 'file'
                    };
                });
            setFiles(fileList);
        } catch (e) {
            console.error(e);
            setFiles([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadFiles();
    }, [currentPath]);

    const handleClear = async () => {
        if (window.confirm("Вы уверены, что хотите очистить всё рабочее пространство?")) {
            await clearSandbox();
            loadFiles();
        }
    };

    const handleRead = async (path) => {
        try {
            const data = await readSandboxFile(path);
            setEditingFile(path);
            setEditContent(data.content);
        } catch (e) {
            alert("Ошибка чтения файла");
        }
    };

    const handleSave = async () => {
        try {
            await writeSandboxFile(editingFile, editContent);
            setEditingFile(null);
            loadFiles();
        } catch (e) {
            alert("Ошибка сохранения");
        }
    };

    return (
        <div className="sandbox-modal">
            <div className="sandbox-content">
                <div className="sandbox-header">
                    <h3>Файловая система модели</h3>
                    <div className="sandbox-actions">
                        <button onClick={handleClear} className="danger-btn">Очистить</button>
                        <button onClick={onClose}>Закрыть</button>
                    </div>
                </div>
                
                {editingFile ? (
                    <div className="file-editor">
                        <h4>Редактирование: {editingFile}</h4>
                        <textarea 
                            value={editContent} 
                            onChange={(e) => setEditContent(e.target.value)}
                            rows={15}
                        />
                        <div className="editor-actions">
                            <button onClick={handleSave}>Сохранить</button>
                            <button onClick={() => setEditingFile(null)}>Отмена</button>
                        </div>
                    </div>
                ) : (
                    <div className="files-list">
                        {loading ? (
                            <div style={{ padding: '20px', textAlign: 'center' }}>Загрузка...</div>
                        ) : (
                            <div style={{ maxHeight: '400px', overflowY: 'auto', background: '#111', borderRadius: '8px', padding: '10px' }}>
                                {Array.isArray(files) && files.length > 0 ? files.map((file, idx) => (
                                    <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px', borderBottom: '1px solid #222' }}>
                                        <span 
                                            onClick={() => file.type === 'dir' ? setCurrentPath(file.path) : handleRead(file.path)}
                                            style={{ cursor: 'pointer', flex: 1, display: 'flex', alignItems: 'center', gap: '8px' }}
                                        >
                                            <span>{file.type === 'dir' ? '📁' : '📄'}</span>
                                            {file.name}
                                        </span>
                                        <div style={{ display: 'flex', gap: '10px' }}>
                                            {file.type === 'file' && (
                                                <button 
                                                    onClick={() => window.open(`http://localhost:8000/sandbox/download?path=${encodeURIComponent(file.path)}`, '_blank')}
                                                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.1rem' }}
                                                    title="Скачать"
                                                >📥</button>
                                            )}
                                            <button 
                                                onClick={async () => {
                                                    if (confirm(`Удалить ${file.name}?`)) {
                                                        await fetch(`http://localhost:8000/sandbox/delete?path=${encodeURIComponent(file.path)}`, { method: 'DELETE' });
                                                        loadFiles();
                                                    }
                                                }}
                                                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.1rem' }}
                                                title="Удалить"
                                            >🗑️</button>
                                        </div>
                                    </div>
                                )) : <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>Пусто</div>}
                            </div>
                        )}
                        <div className="manual-read" style={{ marginTop: '15px', display: 'flex', gap: '10px' }}>
                            <button onClick={() => {
                                const parent = currentPath.split('/').slice(0, -1).join('/') || '/';
                                setCurrentPath(parent);
                            }} disabled={currentPath === '/'}>⬆ Назад</button>
                            <input id="file-path-input" placeholder="/home/quadrogent/file.py" style={{ flex: 1, padding: '8px', borderRadius: '4px', background: '#222', border: '1px solid #333', color: 'white' }} />
                            <button onClick={() => handleRead(document.getElementById('file-path-input').value)}>Открыть</button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
