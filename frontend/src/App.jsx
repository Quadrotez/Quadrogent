import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { 
  fetchModels, 
  fetchRunningModels, 
  streamChat, 
  fetchSettings, 
  saveApiKey,
  fetchChats,
  fetchChat,
  deleteChat
} from "./api";
import SandboxManager from "./SandboxManager";
import "highlight.js/styles/github-dark.css";
import "./App.css";

const STORAGE_KEY = "quadrogent_selected_model";

function MarkdownMessage({ content }) {
  // Ищем все JSON объекты в тексте сообщения
  const jsonRegex = /\{[\s\S]*?\}/g;
  let chatContent = "";
  
  // Очищаем текст от JSON и извлекаем контент из {"mode": "chat", ...}
  const cleanContent = content.replace(jsonRegex, (match) => {
    try {
      const parsed = JSON.parse(match);
      if (parsed.mode === "chat") {
        const c = Array.isArray(parsed.content) ? parsed.content.join('\n') : (parsed.content || "");
        chatContent += c + "\n";
      }
      return ""; // Вырезаем все JSON из основного текста
    } catch (e) {
      return match; // Если не JSON, оставляем как есть
    }
  }).trim();

  // Объединяем очищенный текст и извлеченный чат-контент
  const finalContent = (cleanContent + "\n" + chatContent).trim();

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={{
        a: ({ node, ...props }) => (
          <a {...props} target="_blank" rel="noopener noreferrer" />
        ),
      }}
    >
      {finalContent}
    </ReactMarkdown>
  );
}

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState([]);

  // История чатов
  const [chats, setChats] = useState([]);
  const [currentChatId, setCurrentChatId] = useState(null);

  const [showSettings, setShowSettings] = useState(false);
  const [openrouterConfigured, setOpenrouterConfigured] = useState(false);
  const [openrouterKeyInput, setOpenrouterKeyInput] = useState("");
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState("");
  const [settingsSavedMsg, setSettingsSavedMsg] = useState("");
  const [showSandbox, setShowSandbox] = useState(false);
  const [toolResults, setToolResults] = useState([]);
  const [presentedFiles, setPresentedFiles] = useState([]);

  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);
  const pollTimerRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadModels = () => {
    fetchModels()
      .then((list) => {
        setModels(list);
        if (list.length === 0) return;

        const saved = localStorage.getItem(STORAGE_KEY);
        const isSavedAvailable = saved && list.some((m) => m.name === saved);

        if (isSavedAvailable) {
          setSelectedModel(saved);
        } else if (!list.some((m) => m.name === selectedModel)) {
          setSelectedModel(list[0].name);
        }
      })
      .catch((err) => setError(`Не удалось загрузить модели: ${err.message}`));
  };

  const loadChats = async () => {
    try {
      const list = await fetchChats();
      setChats(list);
    } catch (e) {
      console.error("Ошибка загрузки чатов:", e);
    }
  };

  useEffect(() => {
    loadModels();
    loadChats();
    fetchSettings()
      .then((data) => {
        const orKey = data?.api_keys?.openrouter?.api_key;
        setOpenrouterConfigured(!!orKey);
      })
      .catch(() => {});
  }, []);

  const handleSaveOpenrouterKey = async () => {
    if (!openrouterKeyInput.trim()) {
      setSettingsError("Введите ключ");
      return;
    }
    setSettingsSaving(true);
    setSettingsError("");
    setSettingsSavedMsg("");
    try {
      await saveApiKey("openrouter", openrouterKeyInput.trim());
      setOpenrouterConfigured(true);
      setOpenrouterKeyInput("");
      setSettingsSavedMsg("Ключ сохранён");
      loadModels();
    } catch (e) {
      setSettingsError(e.message || "Не удалось сохранить ключ");
    } finally {
      setSettingsSaving(false);
    }
  };

  const handleModelChange = (e) => {
    const newModel = e.target.value;
    setSelectedModel(newModel);
    localStorage.setItem(STORAGE_KEY, newModel);
  };

  const startPollingModelStatus = (modelName) => {
    stopPollingModelStatus();
    const poll = async () => {
      try {
        const running = await fetchRunningModels();
        const isLoaded = running.some((m) => m.name === modelName);
        if (isLoaded) {
          setStatus("thinking");
          pollTimerRef.current = setTimeout(poll, 500);
        } else {
          setStatus("loading");
          pollTimerRef.current = setTimeout(poll, 500);
        }
      } catch (e) {
        pollTimerRef.current = setTimeout(poll, 1000);
      }
    };
    poll();
  };

  const stopPollingModelStatus = () => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const handleNewChat = () => {
    setCurrentChatId(null);
    setMessages([]);
    setInput("");
    setError("");
    setToolResults([]);
    setPresentedFiles([]);
  };

  const handleSelectChat = async (chatId) => {
    if (isLoading) return;
    setCurrentChatId(chatId);
    setError("");
    setToolResults([]);
    setPresentedFiles([]);
    try {
      const chatData = await fetchChat(chatId);
      setMessages(chatData.messages.map(m => ({ role: m.role, content: m.content })));
      
      // Загружаем результаты инструментов, если они есть
      if (chatData.tool_calls) {
        const results = chatData.tool_calls.map(tc => ({
          tool: tc.tool,
          result: JSON.parse(tc.output || "{}")
        }));
        setToolResults(results);
        
        // Восстанавливаем список презентованных файлов
        const files = [];
        results.forEach(tr => {
          if (tr.tool === "present" && tr.result.exit_code === 0) {
            const stdout = tr.result.stdout || "";
            const pathMatch = stdout.match(/Презентовано: (.*)/);
            const path = pathMatch ? pathMatch[1].trim() : null;
            if (path) {
              const name = path.split('/').pop();
              if (!files.some(f => f.path === path)) {
                files.push({ name, path });
              }
            }
          }
        });
        setPresentedFiles(files);
      }
    } catch (e) {
      console.error(e);
      setError("Не удалось загрузить чат");
    }
  };

  const handleDeleteChat = async (chatId, e) => {
    e.stopPropagation();
    if (isLoading) return;
    try {
      await deleteChat(chatId);
      setChats(prev => prev.filter(c => c.id !== chatId));
      if (currentChatId === chatId) {
        handleNewChat();
      }
    } catch (e) {
      setError("Не удалось удалить чат");
    }
  };

  const uploadFiles = async () => {
    const uploadedPaths = [];
    for (const file of attachedFiles) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch('http://localhost:8000/sandbox/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (data.status === 'ok') {
          uploadedPaths.push(data.path);
        }
      } catch (e) {
        console.error("Ошибка загрузки файла:", e);
      }
    }
    return uploadedPaths;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if ((!input.trim() && attachedFiles.length === 0) || isLoading) return;
    if (!selectedModel) {
      setError("Выберите модель");
      return;
    }

    setError("");
    setIsLoading(true);

    // Сначала загружаем файлы
    let finalInput = input.trim();
    if (attachedFiles.length > 0) {
      const paths = await uploadFiles();
      if (paths.length > 0) {
        finalInput += `\n\n[Загружены файлы: ${paths.join(', ')}]`;
      }
    }

    const userMessage = { role: "user", content: finalInput };
    setAttachedFiles([]); // Очищаем после отправки
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setIsLoading(true);

    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const isOpenrouterModel = selectedModel.startsWith("openrouter:");

    let initialStatus = "thinking";
    if (!isOpenrouterModel) {
      initialStatus = "loading";
      try {
        const running = await fetchRunningModels();
        if (running.some((m) => m.name === selectedModel)) {
          initialStatus = "thinking";
        }
      } catch (e) {}
    }
    setStatus(initialStatus);

    if (initialStatus === "loading") {
      startPollingModelStatus(selectedModel);
    }

    let firstChunkReceived = false;

    setToolResults([]);
    await streamChat(
      selectedModel,
      newMessages,
      (chunk) => {
        if (!firstChunkReceived) {
          firstChunkReceived = true;
          stopPollingModelStatus();
          setStatus("generating");
        }

        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          const newContent = last.content + chunk;
          
          updated[updated.length - 1] = {
            ...last,
            content: newContent,
          };
          return updated;
        });
      },
      () => {
        stopPollingModelStatus();
        setIsLoading(false);
        setStatus("idle");
        abortControllerRef.current = null;
        loadChats(); // Обновляем список чатов (может измениться порядок)
      },
      async (errMsg) => {
        // Проверка на 429 Rate Limit в сообщении об ошибке
        try {
          const errorData = JSON.parse(errMsg);
          const retryAfter = errorData.metadata?.retry_after_seconds || errorData.retry_after_seconds;
          if (retryAfter) {
            const waitTime = (parseFloat(retryAfter) + 1) * 1000;
            const retryMsg = `\n\n*Система: Превышен лимит запросов. Повторная попытка через ${Math.round(waitTime/1000)} сек...*\n\n`;
            
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, content: last.content + retryMsg };
              return updated;
            });

            await new Promise(resolve => setTimeout(resolve, waitTime));
            // Рекурсивный вызов handleSubmit для повтора
            setIsLoading(false);
            return handleSubmit({ preventDefault: () => {} });
          }
        } catch (e) {
          // Если не JSON или нет retry_after, обрабатываем как обычную ошибку
        }

        stopPollingModelStatus();
        setError(errMsg);
        setIsLoading(false);
        setStatus("idle");
        abortControllerRef.current = null;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && !last.content) {
            return prev.slice(0, -1);
          }
          return prev;
        });
      },
      controller.signal,
      currentChatId,
      (newChatId) => {
        if (!currentChatId) {
          setCurrentChatId(newChatId);
        }
      },
      (toolResult) => {
        setToolResults(prev => [...prev, toolResult]);
        if (toolResult.tool === "present" && toolResult.result.exit_code === 0) {
            // Извлекаем путь из "Презентовано: /home/quadrogent/output/filename"
            const stdout = toolResult.result.stdout || "";
            const pathMatch = stdout.match(/Презентовано: (.*)/);
            const path = pathMatch ? pathMatch[1].trim() : null;
            
            if (path) {
                const name = path.split('/').pop();
                setPresentedFiles(prev => {
                    // Избегаем дубликатов
                    if (prev.some(f => f.path === path)) return prev;
                    return [...prev, { name, path }];
                });
            }
        }
      }
    );
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
  };

  const handleInputKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleFileAttach = (e) => {
    const files = Array.from(e.target.files);
    setAttachedFiles(prev => [...prev, ...files]);
  };

  const handlePaste = (e) => {
    const items = e.clipboardData.items;
    const files = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].kind === 'file') {
        files.push(items[i].getAsFile());
      }
    }
    if (files.length > 0) {
      setAttachedFiles(prev => [...prev, ...files]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      setAttachedFiles(prev => [...prev, ...files]);
    }
  };

  const autoResizeInput = (e) => {
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  const getStatusText = () => {
    switch (status) {
      case "loading": return "Загрузка модели...";
      case "thinking": return "Думаю...";
      case "generating": return "Генерирую...";
      default: return "";
    }
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>Чаты</h2>
          <button className="new-chat-btn" onClick={handleNewChat} disabled={isLoading}>
            + Новый
          </button>
        </div>
        <div className="chat-list">
          {chats.length === 0 && (
            <div style={{ padding: "1rem", color: "#666", fontSize: "0.9rem", textAlign: "center" }}>
              Нет сохраненных чатов
            </div>
          )}
          {chats.map((chat) => (
            <div
              key={chat.id}
              className={`chat-item ${currentChatId === chat.id ? "active" : ""}`}
              onClick={() => handleSelectChat(chat.id)}
            >
              <span className="chat-item-title">{chat.title}</span>
              <button
                className="chat-item-delete"
                onClick={(e) => handleDeleteChat(chat.id, e)}
                title="Удалить чат"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </aside>

      <div className="main-content">
        <header className="header">
          <h1>Quadrogent</h1>
          <div className="header-controls">
            <div className="model-selector">
              <label htmlFor="model">Модель:</label>
              <select
                id="model"
                value={selectedModel}
                onChange={handleModelChange}
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
              className="settings-button"
              onClick={() => setShowSandbox(true)}
              title="Файлы песочницы"
              style={{ marginRight: '8px' }}
            >
              📁
            </button>
            <button
              type="button"
              className="settings-button"
              onClick={() => setShowSettings(true)}
              title="Настройки"
            >
              ⚙
            </button>
          </div>
        </header>

        {showSandbox && (
          <div className="modal-overlay" onClick={() => setShowSandbox(false)}>
            <SandboxManager onClose={() => setShowSandbox(false)} />
          </div>
        )}

        {showSettings && (
          <div className="modal-overlay" onClick={() => setShowSettings(false)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <h2>Настройки</h2>
              <div className="settings-section">
                <h3>OpenRouter</h3>
                <p className="settings-hint">
                  {openrouterConfigured
                    ? "Ключ уже сохранён. Введите новый, чтобы заменить его."
                    : "Добавьте API-ключ, чтобы получить доступ к моделям OpenRouter."}
                </p>
                <input
                  type="password"
                  className="settings-input"
                  placeholder="sk-or-v1-..."
                  value={openrouterKeyInput}
                  onChange={(e) => setOpenrouterKeyInput(e.target.value)}
                />
                {settingsError && <div className="settings-error">{settingsError}</div>}
                {settingsSavedMsg && <div className="settings-success">{settingsSavedMsg}</div>}
                <div className="settings-actions">
                  <button
                    type="button"
                    className="send-button"
                    onClick={handleSaveOpenrouterKey}
                    disabled={settingsSaving}
                  >
                    {settingsSaving ? "Сохранение..." : "Сохранить"}
                  </button>
                  <button type="button" className="settings-close" onClick={() => setShowSettings(false)}>
                    Закрыть
                  </button>
                </div>
                <p className="settings-hint settings-hint--small">
                  Ключ хранится в базе данных бэкенда (таблица api_keys) и никогда не передаётся третьим сторонам, кроме самого OpenRouter.
                </p>
              </div>
            </div>
          </div>
        )}

        <main className="chat-container">
          <div className="messages">
            {messages.length === 0 && (
              <div className="empty-state">
                <p>Начните диалог с Quadrogent</p>
                {models.length === 0 && (
                  <p className="hint">
                    Убедитесь, что Ollama запущена и в ней есть хотя бы одна модель
                  </p>
                )}
              </div>
            )}

            {messages.map((msg, index) => (
              <div key={index} className={`message ${msg.role}`}>
                <div className="message-content">
                  {msg.content ? (
                    msg.role === "assistant" ? (
                      <MarkdownMessage content={msg.content} />
                    ) : (
                      msg.content
                    )
                  ) : msg.role === "assistant" && isLoading && index === messages.length - 1 ? (
                    <span className="typing">●●●</span>
                  ) : (
                    " "
                  )}
                </div>
                {msg.role === "assistant" && isLoading && index === messages.length - 1 && status !== "idle" && (
                  <div className="status-indicator">
                    <span className="status-dot"></span>
                    {getStatusText()}
                  </div>
                )}
              </div>
            ))}

            {toolResults.length > 0 && (
              <div className="tool-results" style={{ marginTop: '15px' }}>
                  {toolResults.map((tr, i) => (
                      <details key={i} className="tool-call-details" style={{ marginBottom: '8px', background: '#222', borderRadius: '6px', border: '1px solid #333' }}>
                          <summary style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <span style={{ color: tr.result.exit_code === 0 ? '#4ade80' : '#f87171' }}>
                                {tr.result.exit_code === 0 ? "✅" : "❌"}
                              </span>
                              <span style={{ fontWeight: '600' }}>Инструмент: {tr.tool}</span>
                              <span style={{ fontSize: '0.8rem', color: '#888', marginLeft: 'auto' }}>
                                {tr.result.exit_code === 0 ? "Успешно" : "Ошибка"}
                              </span>
                          </summary>
                          <div style={{ padding: '10px', borderTop: '1px solid #333', background: '#111' }}>
                              {tr.result.stdout && (
                                  <div style={{ marginBottom: '5px' }}>
                                      <div style={{ fontSize: '0.75rem', color: '#888', marginBottom: '2px' }}>Вывод:</div>
                                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '0.8rem', color: '#ccc' }}>{tr.result.stdout}</pre>
                                  </div>
                              )}
                              {tr.result.stderr && (
                                  <div style={{ marginBottom: '5px' }}>
                                      <div style={{ fontSize: '0.75rem', color: '#f87171', marginBottom: '2px' }}>Ошибка (stderr):</div>
                                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '0.8rem', color: '#fca5a5' }}>{tr.result.stderr}</pre>
                                  </div>
                              )}
                              {tr.result.error && (
                                  <div style={{ color: '#f87171', fontSize: '0.8rem' }}>{tr.result.error}</div>
                              )}
                          </div>
                      </details>
                  ))}
              </div>
            )}

            {presentedFiles.length > 0 && !isLoading && (
              <div className="presented-files" style={{ marginTop: '20px', padding: '15px', background: 'rgba(0, 102, 204, 0.1)', borderRadius: '10px', border: '1px solid #0066cc' }}>
                  <h4 style={{ margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>🎁</span> Презентованные файлы
                  </h4>
                  <div className="files-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
                      {presentedFiles.map((file, i) => (
                          <div key={i} className="file-card" style={{ background: '#222', padding: '10px', borderRadius: '6px', display: 'flex', flexDirection: 'column', gap: '8px', border: '1px solid #333' }}>
                              <div style={{ fontSize: '0.9rem', fontWeight: '500', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={file.path}>
                                {file.name}
                              </div>
                              <button 
                                onClick={() => {
                                  const url = `http://localhost:8000/sandbox/download?path=${encodeURIComponent(file.path)}`;
                                  window.open(url, '_blank');
                                }}
                                className="download-btn"
                                style={{ background: '#0066cc', border: 'none', color: 'white', padding: '6px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: '600' }}
                              >
                                Скачать файл
                              </button>
                          </div>
                      ))}
                  </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {error && <div className="error-banner">{error}</div>}

          <form 
            className={`input-form ${isDragging ? 'dragging' : ''}`} 
            onSubmit={handleSubmit}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {attachedFiles.length > 0 && (
              <div className="attached-files-preview" style={{ display: 'flex', gap: '10px', padding: '10px', background: '#1a1a1a', borderTop: '1px solid #333', flexWrap: 'wrap' }}>
                {attachedFiles.map((file, i) => (
                  <div key={i} style={{ background: '#333', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '5px' }}>
                    📄 {file.name}
                    <button type="button" onClick={() => setAttachedFiles(prev => prev.filter((_, idx) => idx !== i))} style={{ background: 'none', border: 'none', color: '#ff4d4d', cursor: 'pointer', padding: '0 2px' }}>✕</button>
                  </div>
                ))}
              </div>
            )}
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '10px', padding: '10px' }}>
              <label className="attach-button" style={{ cursor: 'pointer', fontSize: '1.2rem', padding: '8px' }} title="Прикрепить файл">
                📎
                <input type="file" multiple onChange={handleFileAttach} style={{ display: 'none' }} />
              </label>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  autoResizeInput(e);
                }}
                onKeyDown={handleInputKeyDown}
                onPaste={handlePaste}
                placeholder={isDragging ? "Отпустите файлы здесь" : (selectedModel ? "Введите сообщение... (Shift+Enter — новая строка)" : "Загрузка моделей...")}
                className="message-input"
                rows={1}
                disabled={isLoading || !selectedModel}
                style={{ flex: 1 }}
              />
              {isLoading ? (
                <button type="button" onClick={handleStop} className="stop-button">
                  Стоп
                </button>
              ) : (
                <button type="submit" className="send-button" disabled={!selectedModel && attachedFiles.length === 0}>
                  Отправить
                </button>
              )}
            </div>
          </form>
        </main>
      </div>
    </div>
  );
}

export default App;