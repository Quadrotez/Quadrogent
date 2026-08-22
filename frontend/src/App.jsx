import { useState, useEffect, useRef } from "react";
import {
  fetchModels,
  fetchRunningModels,
  streamChat,
  fetchSettings,
  saveSetting,
  fetchChats,
  fetchChat,
  deleteChat,
} from "./api";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import MessageList from "./components/MessageList";
import InputForm from "./components/InputForm";
import ProfilePanel from "./components/ProfilePanel";
import ProviderManager from "./components/ProviderManager";
import SandboxManager from "./SandboxManager";
import "./App.css";

const STORAGE_KEY = "quadrogent_selected_model";
const SANDBOX_MODE_KEY = "quadrogent_sandbox_mode";

/**
 * Структура элемента массива messages:
 * {
 *   role: "user" | "assistant",
 *   content: string,
 *   toolCallsBefore?: Array<{ tool, input, result }>
 * }
 *
 * toolCallsBefore — вызовы инструментов, которые произошли ДО того,
 * как модель написала этот текстовый ответ. Они отображаются прямо перед
 * текстом сообщения, сохраняя хронологический порядок.
 */

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState([]);

  const [chats, setChats] = useState([]);
  const [currentChatId, setCurrentChatId] = useState(() => {
    const m = window.location.pathname.match(/^\/chat\/(\d+)$/);
    return m ? parseInt(m[1], 10) : null;
  });

  const [showProviders, setShowProviders] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState("");
  const [settingsSavedMsg, setSettingsSavedMsg] = useState("");
  const [userName, setUserName] = useState("");
  const [userInfo, setUserInfo] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [modelSettings, setModelSettings] = useState({
    model_num_ctx: "8192",
    model_temperature: "0.0",
    model_top_p: "0.9",
    model_max_tokens: "4096",
    generate_titles: "false",
    multi_command: "true",
    max_consecutive_tool_calls: "15",
    self_context: "",
    tool_calling_mode: "native",
    search_providers: "duckduckgo",
    search_proxy: "",
    web_fetch_enabled: "true",
    web_search_fetch_results: "true",
  });

  const [sandboxOpen, setSandboxOpen] = useState(false);
  const [sandboxMode, setSandboxMode] = useState(
    () => localStorage.getItem(SANDBOX_MODE_KEY) || "panel"
  );

  const changeSandboxMode = (mode) => {
    setSandboxMode(mode);
    localStorage.setItem(SANDBOX_MODE_KEY, mode);
  };

  const abortControllerRef = useRef(null);
  const pollTimerRef = useRef(null);
  const pendingToolCallsRef = useRef([]);
  const needsNewlineRef = useRef(false);

  // --- Загрузка моделей ---
  const loadModels = () => {
    fetchModels()
      .then(({ models: list, errors }) => {
        setModels(list);
        if (list.length === 0) return;
        const saved = localStorage.getItem(STORAGE_KEY);
        const isSavedAvailable = saved && list.some((m) => m.name === saved);
        if (isSavedAvailable) {
          setSelectedModel(saved);
        } else if (!list.some((m) => m.name === selectedModel)) {
          setSelectedModel(list[0].name);
        }
        // Показываем ошибки провайдеров если есть
        if (errors && Object.keys(errors).length > 0) {
          const msgs = Object.entries(errors)
            .map(([k, v]) => `${k}: ${v}`)
            .join("; ");
          setError(`Ошибки загрузки моделей: ${msgs}`);
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
        if (data?.settings) {
          const { user_name, user_info, system_prompt, ...llmSettings } = data.settings;
          setModelSettings((prev) => ({
            ...prev,
            ...llmSettings,
          }));
          if (user_name !== undefined) setUserName(user_name || "");
          if (user_info !== undefined) setUserInfo(user_info || "");
          if (system_prompt !== undefined) setSystemPrompt(system_prompt || "");
        }
      })
      .catch(() => {});

    // Load chat from URL if present
    const m = window.location.pathname.match(/^\/chat\/(\d+)$/);
    if (m) {
      const chatId = parseInt(m[1], 10);
      loadChatById(chatId);
    }
  }, []);

  // --- Browser back/forward ---
  useEffect(() => {
    const onPopState = () => {
      const m = window.location.pathname.match(/^\/chat\/(\d+)$/);
      const chatId = m ? parseInt(m[1], 10) : null;
      if (chatId !== currentChatId) {
        setCurrentChatId(chatId);
        if (chatId) {
          loadChatById(chatId);
        } else {
          setMessages([]);
          setInput("");
        }
      }
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [currentChatId, isLoading]);

  // --- Настройки ---
  const handleSaveProfile = async () => {
    setSettingsSaving(true);
    setSettingsError("");
    setSettingsSavedMsg("");
    try {
      await saveSetting("user_name", userName);
      await saveSetting("user_info", userInfo);
      await saveSetting("system_prompt", systemPrompt);
      const PROFILE_KEYS = new Set(["user_name", "user_info", "system_prompt"]);
      for (const [key, value] of Object.entries(modelSettings)) {
        if (PROFILE_KEYS.has(key)) continue;
        await saveSetting(key, value);
      }
      setSettingsSavedMsg("Профиль сохранён");
    } catch (e) {
      setSettingsError(e.message || "Не удалось сохранить профиль");
    } finally {
      setSettingsSaving(false);
    }
  };

  const handleModelSelect = (modelName) => {
    setSelectedModel(modelName);
    localStorage.setItem(STORAGE_KEY, modelName);
  };

  // --- Polling статуса модели ---
  const startPollingModelStatus = (modelName) => {
    stopPollingModelStatus();
    const poll = async () => {
      try {
        const running = await fetchRunningModels();
        setStatus(running.some((m) => m.name === modelName) ? "thinking" : "loading");
        pollTimerRef.current = setTimeout(poll, 500);
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

  // --- Управление чатами ---
  const handleNewChat = () => {
    setCurrentChatId(null);
    setMessages([]);
    setInput("");
    setError("");
    window.history.pushState({}, "", "/new");
  };

  const loadChatById = async (chatId) => {
    setError("");
    try {
      const chatData = await fetchChat(chatId);

      const tcByMsgId = {};
      for (const tc of chatData.tool_calls || []) {
        if (!tcByMsgId[tc.message_id]) tcByMsgId[tc.message_id] = [];
        let parsedInput = tc.input;
        try { parsedInput = JSON.parse(tc.input); } catch {}
        let parsedOutput = tc.output;
        try { parsedOutput = JSON.parse(tc.output); } catch {}
        tcByMsgId[tc.message_id].push({
          tool: tc.tool,
          input: parsedInput,
          result: parsedOutput,
        });
      }

      const presentedFilesByMsgId = {};
      for (const tc of chatData.tool_calls || []) {
        if (tc.tool === "present") {
          let output = tc.output;
          try { output = JSON.parse(tc.output); } catch {}
          if (output?.exit_code === 0) {
            const stdout = output.stdout || "";
            const pathMatch = stdout.match(/Презентовано: (.*)/);
            const path = pathMatch ? pathMatch[1].trim() : null;
            if (path) {
              if (!presentedFilesByMsgId[tc.message_id]) presentedFilesByMsgId[tc.message_id] = [];
              const name = path.split("/").pop();
              if (!presentedFilesByMsgId[tc.message_id].some((f) => f.path === path)) {
                presentedFilesByMsgId[tc.message_id].push({ name, path });
              }
            }
          }
        }
      }

      const rawMessages = chatData.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        toolCalls: tcByMsgId[m.id] || [],
      }));

      const builtMessages = [];
      let pendingTCs = [];

      for (const msg of rawMessages) {
        if (msg.role === "assistant") {
          // Tool calls из БД привязаны к msg.id (ToolCall.message_id = msg.id)
          // Дополнительно берём pendingTCs от предыдущего сообщения (legacy)
          const allTCs = [...pendingTCs, ...msg.toolCalls];
          pendingTCs = [];

          if (allTCs.length > 0 && !msg.content) {
            // Только tool calls без текста — tool calls идут СВЕРХУ, текста нет
            builtMessages.push({
              role: "assistant",
              content: "",
              toolCallsBefore: allTCs,
              presentedFiles: presentedFilesByMsgId[msg.id] || [],
            });
          } else if (allTCs.length > 0 && msg.content) {
            // И текст, и tool calls — tool calls сверху, текст снизу
            builtMessages.push({
              role: "assistant",
              content: msg.content,
              toolCallsBefore: allTCs,
              presentedFiles: presentedFilesByMsgId[msg.id] || [],
            });
          } else {
            // Только текст
            builtMessages.push({
              role: "assistant",
              content: msg.content,
              toolCallsBefore: [],
              presentedFiles: presentedFilesByMsgId[msg.id] || [],
            });
          }
        } else {
          if (pendingTCs.length > 0) {
            builtMessages.push({
              role: "assistant",
              content: "",
              toolCallsBefore: pendingTCs,
            });
            pendingTCs = [];
          }
          builtMessages.push({ role: msg.role, content: msg.content });
        }
      }

      if (pendingTCs.length > 0) {
        builtMessages.push({
          role: "assistant",
          content: "",
          toolCallsBefore: pendingTCs,
        });
      }

      setMessages(builtMessages);
    } catch (e) {
      console.error(e);
      setError("Не удалось загрузить чат");
    }
  };

  const handleSelectChat = async (chatId) => {
    if (isLoading) return;
    setCurrentChatId(chatId);
    if (chatId) {
      window.history.pushState({ chatId }, "", `/chat/${chatId}`);
    } else {
      window.history.pushState({}, "", "/");
    }
    await loadChatById(chatId);
  };

  const handleExportChat = async (chatId, e) => {
    e.stopPropagation();
    try {
      const chatData = await fetchChat(chatId);

      const tcByMsgId = {};
      for (const tc of chatData.tool_calls || []) {
        if (!tcByMsgId[tc.message_id]) tcByMsgId[tc.message_id] = [];
        let parsedInput = tc.input;
        try { parsedInput = JSON.parse(tc.input); } catch {}
        let parsedOutput = tc.output;
        try { parsedOutput = JSON.parse(tc.output); } catch {}
        tcByMsgId[tc.message_id].push({
          tool: tc.tool,
          input: parsedInput,
          result: parsedOutput,
          status: tc.status,
        });
      }

      const messages = [];
      for (const m of chatData.messages || []) {
        if (m.role === "assistant") {
          messages.push({
            role: m.role,
            content: m.content,
            toolCalls: tcByMsgId[m.id] || [],
          });
        } else {
          messages.push({ role: m.role, content: m.content });
        }
      }

      const exportData = {
        chat_id: chatData.id,
        title: chatData.title,
        exported_at: new Date().toISOString(),
        messages,
      };

      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeTitle = (chatData.title || "chat").replace(/[^a-zA-Zа-яА-Я0-9_\-]/g, "_").slice(0, 50);
      a.download = `${safeTitle}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError("Не удалось экспортировать чат: " + err.message);
    }
  };

  const handleDeleteChat = async (chatId, e) => {
    e.stopPropagation();
    if (isLoading) return;
    try {
      await deleteChat(chatId);
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      if (currentChatId === chatId) handleNewChat();
    } catch (e) {
      setError("Не удалось удалить чат");
    }
  };

  // --- Загрузка файлов ---
  const uploadFiles = async () => {
    const uploadedPaths = [];
    for (const file of attachedFiles) {
      const formData = new FormData();
      formData.append("file", file);
      try {
        const res = await fetch("http://localhost:8000/sandbox/upload", {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (data.status === "ok") uploadedPaths.push(data.path);
      } catch (e) {
        console.error("Ошибка загрузки файла:", e);
      }
    }
    return uploadedPaths;
  };

  // --- Отправка сообщения ---
  const handleSubmit = async (e) => {
    e.preventDefault();
    if ((!input.trim() && attachedFiles.length === 0) || isLoading) return;
    if (!selectedModel) {
      setError("Выберите модель");
      return;
    }

    setError("");
    setIsLoading(true);
    pendingToolCallsRef.current = [];

    let finalInput = input.trim();
    if (attachedFiles.length > 0) {
      const paths = await uploadFiles();
      if (paths.length > 0) {
        finalInput += `\n\n[Загружены файлы: ${paths.join(", ")}]`;
      }
    }

    const userMessage = { role: "user", content: finalInput };
    setAttachedFiles([]);
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");

    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", toolCallsBefore: [] },
    ]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Для облачных провайдеров не нужно polling — они отвечают сразу
    const isCloudProvider = selectedModel.includes(":");
    let initialStatus = "thinking";
    if (!isCloudProvider) {
      initialStatus = "loading";
      try {
        const running = await fetchRunningModels();
        if (running.some((m) => m.name === selectedModel)) initialStatus = "thinking";
      } catch (e) {}
    }
    setStatus(initialStatus);
    if (initialStatus === "loading") startPollingModelStatus(selectedModel);

    let firstChunkReceived = false;

    const apiMessages = newMessages.map(({ role, content }) => ({ role, content }));

    await streamChat(
      selectedModel,
      apiMessages,
      // onChunk
      (chunk) => {
        if (!firstChunkReceived) {
          firstChunkReceived = true;
          stopPollingModelStatus();
          setStatus("generating");
        }
        if (needsNewlineRef.current) {
          needsNewlineRef.current = false;
          chunk = "\n" + chunk;
        }
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant") {
            const buffered = pendingToolCallsRef.current;
            pendingToolCallsRef.current = [];
            updated[updated.length - 1] = {
              ...last,
              content: last.content + chunk,
              toolCallsBefore: [...(last.toolCallsBefore || []), ...buffered],
            };
          }
          return updated;
        });
      },
      // onDone
      () => {
        stopPollingModelStatus();
        setIsLoading(false);
        setStatus("idle");
        abortControllerRef.current = null;
        pendingToolCallsRef.current = [];
        needsNewlineRef.current = false;
        loadChats();
      },
      // onError
      async (errMsg) => {
        try {
          const errorData = JSON.parse(errMsg);
          const retryAfter =
            errorData.metadata?.retry_after_seconds || errorData.retry_after_seconds;
          if (retryAfter) {
            const waitTime = (parseFloat(retryAfter) + 1) * 1000;
            const retryMsg = `\n\n*Система: Превышен лимит запросов. Повторная попытка через ${Math.round(waitTime / 1000)} сек...*\n\n`;
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last?.role === "assistant") {
                updated[updated.length - 1] = { ...last, content: last.content + retryMsg };
              }
              return updated;
            });
            await new Promise((resolve) => setTimeout(resolve, waitTime));
            setIsLoading(false);
            return handleSubmit({ preventDefault: () => {} });
          }
        } catch (e) {}

        stopPollingModelStatus();
        setError(errMsg);
        setIsLoading(false);
        setStatus("idle");
        abortControllerRef.current = null;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && !last.content && !last.toolCallsBefore?.length) {
            return prev.slice(0, -1);
          }
          return prev;
        });
      },
      controller.signal,
      currentChatId,
      // onChatId
      (newChatId) => {
        if (!currentChatId) {
          setCurrentChatId(newChatId);
          window.history.pushState({ chatId: newChatId }, "", `/chat/${newChatId}`);
        }
      },
      // onToolResult
      (toolResult) => {
        const { tool, input: toolInput, result } = toolResult;
        needsNewlineRef.current = true;

        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          const last = updated[lastIdx];

          if (last?.role === "assistant") {
            const tcs = last.toolCallsBefore || [];
            // Find a pending entry (result === null) with matching tool name and update it
            const pendingIdx = tcs.findIndex(
              (tc) => tc.tool === tool && tc.result === null
            );
            if (pendingIdx !== -1) {
              const newTCs = [...tcs];
              newTCs[pendingIdx] = { ...newTCs[pendingIdx], result };
              updated[lastIdx] = { ...last, toolCallsBefore: newTCs };
              return updated;
            }
            // No pending entry found — append new
            updated[lastIdx] = {
              ...last,
              toolCallsBefore: [...tcs, { tool, input: toolInput, result }],
            };
            return updated;
          }

          // No assistant message yet — buffer
          pendingToolCallsRef.current.push({ tool, input: toolInput, result });
          return prev;
        });

        if (tool === "present" && result?.exit_code === 0) {
          const stdout = result.stdout || "";
          const pathMatch = stdout.match(/Презентовано: (.*)/);
          const path = pathMatch ? pathMatch[1].trim() : null;
          if (path) {
            const name = path.split("/").pop();
            setMessages((prev) => {
              const updated = [...prev];
              const lastIdx = updated.length - 1;
              const last = updated[lastIdx];
              if (last?.role === "assistant") {
                const existingFiles = last.presentedFiles || [];
                if (!existingFiles.some((f) => f.path === path)) {
                  updated[lastIdx] = {
                    ...last,
                    presentedFiles: [...existingFiles, { name, path }],
                  };
                }
              }
              return updated;
            });
          }
        }
      },
      // onTitle
      (titleData) => {
        const title = typeof titleData === "string" ? titleData : titleData.title;
        const chatId = typeof titleData === "object" ? titleData.chat_id : currentChatId;
        setChats((prev) =>
          prev.map((c) =>
            c.id === chatId ? { ...c, title } : c
          )
        );
      },
      // onToolExecuting
      (toolExec) => {
        if (!firstChunkReceived) {
          firstChunkReceived = true;
          stopPollingModelStatus();
          setStatus("generating");
        }
        const { tool, input: toolInput } = toolExec;
        const tcEntry = { tool, input: toolInput, result: null };

        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          const last = updated[lastIdx];

          if (last?.role === "assistant") {
            updated[lastIdx] = {
              ...last,
              toolCallsBefore: [...(last.toolCallsBefore || []), tcEntry],
            };
          }
          return updated;
        });
      }
    );
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
  };

  return (
    <div className="app">
      <Sidebar
        chats={chats}
        currentChatId={currentChatId}
        isLoading={isLoading}
        userName={userName}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
        onExportChat={handleExportChat}
        onOpenProfile={() => setShowProfile(true)}
      />

      <div className="main-content">
        <Header
          models={models}
          selectedModel={selectedModel}
          isLoading={isLoading}
          onModelSelect={handleModelSelect}
          onOpenProviders={() => setShowProviders(true)}
          sandboxOpen={sandboxOpen}
          sandboxMode={sandboxMode}
          onOpenSandbox={() => setSandboxOpen(true)}
        />

        {showProfile && (
          <ProfilePanel
            userName={userName}
            setUserName={setUserName}
            userInfo={userInfo}
            setUserInfo={setUserInfo}
            systemPrompt={systemPrompt}
            setSystemPrompt={setSystemPrompt}
            modelSettings={modelSettings}
            setModelSettings={setModelSettings}
            saving={settingsSaving}
            error={settingsError}
            savedMsg={settingsSavedMsg}
            onSave={handleSaveProfile}
            onClose={() => setShowProfile(false)}
          />
        )}

        {showProviders && (
          <ProviderManager
            onSaved={() => {
              loadModels();
            }}
            onClose={() => setShowProviders(false)}
          />
        )}

        <main className={`chat-container ${sandboxOpen && sandboxMode === "panel" ? "chat-container--with-panel" : ""}`}>
          <MessageList
            messages={messages}
            isLoading={isLoading}
            status={status}
            models={models}
          />

          {error && <div className="error-banner">{error}</div>}

          <InputForm
            input={input}
            setInput={setInput}
            isLoading={isLoading}
            selectedModel={selectedModel}
            attachedFiles={attachedFiles}
            setAttachedFiles={setAttachedFiles}
            isDragging={isDragging}
            setIsDragging={setIsDragging}
            onSubmit={handleSubmit}
            onStop={handleStop}
          />
        </main>
      </div>

      {sandboxOpen && sandboxMode === "panel" && (
        <SandboxManager
          mode="panel"
          onClose={() => setSandboxOpen(false)}
          onToggleMode={() => changeSandboxMode("modal")}
        />
      )}

      {sandboxOpen && sandboxMode === "modal" && (
        <SandboxManager
          mode="modal"
          onClose={() => setSandboxOpen(false)}
          onToggleMode={() => changeSandboxMode("panel")}
        />
      )}
    </div>
  );
}
