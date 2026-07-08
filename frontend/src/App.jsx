import { useState, useEffect, useRef } from "react";
import {
  fetchModels,
  fetchRunningModels,
  streamChat,
  fetchSettings,
  saveApiKey,
  fetchChats,
  fetchChat,
  deleteChat,
} from "./api";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import MessageList from "./components/MessageList";
import InputForm from "./components/InputForm";
import SettingsModal from "./components/SettingsModal";
import SandboxManager from "./SandboxManager";
import "./App.css";

const STORAGE_KEY = "quadrogent_selected_model";

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
  const [currentChatId, setCurrentChatId] = useState(null);

  const [showSettings, setShowSettings] = useState(false);
  const [openrouterConfigured, setOpenrouterConfigured] = useState(false);
  const [openrouterKeyInput, setOpenrouterKeyInput] = useState("");
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState("");
  const [settingsSavedMsg, setSettingsSavedMsg] = useState("");
  const [modelSettings, setModelSettings] = useState({
    model_num_ctx: "8192",
    model_temperature: "0.0",
    model_top_p: "0.9",
    model_max_tokens: "4096",
  });

  const [showSandbox, setShowSandbox] = useState(false);

  const abortControllerRef = useRef(null);
  const pollTimerRef = useRef(null);

  // --- Загрузка моделей ---
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
        
        if (data?.settings) {
          setModelSettings((prev) => ({
            ...prev,
            ...data.settings,
          }));
        }
      })
      .catch(() => {});
  }, []);

  // --- Настройки ---
  const handleSaveSettings = async () => {
    setSettingsSaving(true);
    setSettingsError("");
    setSettingsSavedMsg("");
    try {
      // Сохраняем API ключ если введен
      if (openrouterKeyInput.trim()) {
        await saveApiKey("openrouter", openrouterKeyInput.trim());
        setOpenrouterConfigured(true);
        setOpenrouterKeyInput("");
      }

      // Сохраняем параметры модели
      const { saveSetting } = await import("./api");
      for (const [key, value] of Object.entries(modelSettings)) {
        await saveSetting(key, value);
      }

      setSettingsSavedMsg("Настройки сохранены");
      loadModels();
    } catch (e) {
      setSettingsError(e.message || "Не удалось сохранить настройки");
    } finally {
      setSettingsSaving(false);
    }
  };

  const handleModelChange = (e) => {
    const newModel = e.target.value;
    setSelectedModel(newModel);
    localStorage.setItem(STORAGE_KEY, newModel);
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
  };

  const handleSelectChat = async (chatId) => {
    if (isLoading) return;
    setCurrentChatId(chatId);
    setError("");
    try {
      const chatData = await fetchChat(chatId);

      // Строим карту: message_id -> tool_calls[]
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

      // Привязываем presented files к конкретным сообщениям
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

      // Строим список сообщений с прикреплёнными tool-calls.
      // tool-calls прикреплены к assistant-сообщению, которое их вызвало.
      // Мы показываем их ПЕРЕД следующим ответом ассистента (хронологический порядок).
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
          builtMessages.push({
            role: "assistant",
            content: msg.content,
            toolCallsBefore: pendingTCs,
            presentedFiles: presentedFilesByMsgId[msg.id] || [],
          });
          // tool-calls этого сообщения будут показаны перед следующим
          pendingTCs = msg.toolCalls;
        } else {
          // Перед user-сообщением: если остались pending tool-calls — добавляем их
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

      // Если остались tool-calls после последнего сообщения
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

    // Добавляем пустое сообщение ассистента (будет заполнено чанками)
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", toolCallsBefore: [] },
    ]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const isOpenrouterModel = selectedModel.startsWith("openrouter:");
    let initialStatus = "thinking";
    if (!isOpenrouterModel) {
      initialStatus = "loading";
      try {
        const running = await fetchRunningModels();
        if (running.some((m) => m.name === selectedModel)) initialStatus = "thinking";
      } catch (e) {}
    }
    setStatus(initialStatus);
    if (initialStatus === "loading") startPollingModelStatus(selectedModel);

    let firstChunkReceived = false;

    // Сообщения для API (без UI-полей)
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
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + chunk,
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
        if (!currentChatId) setCurrentChatId(newChatId);
      },
      // onToolResult — встраиваем tool-call в поток сообщений в реальном времени
      (toolResult) => {
        const { tool, result } = toolResult;

        // Извлекаем input из текущего контента последнего assistant-сообщения
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          const last = updated[lastIdx];
          
          let toolInput = null;
          if (last?.role === "assistant" && last.content) {
            let jsonStr = null;
            const markdownMatch = last.content.match(/```(?:json)?\n([\s\S]*?)\n```/);
            if (markdownMatch) {
              jsonStr = markdownMatch[1];
            } else {
              const start = last.content.indexOf("{");
              const end = last.content.lastIndexOf("}");
              if (start !== -1 && end !== -1) {
                jsonStr = last.content.slice(start, end + 1);
              }
            }

            if (jsonStr) {
              try {
                const parsed = JSON.parse(jsonStr);
                if (parsed.mode === "tool_calling") {
                  toolInput = Object.fromEntries(
                    Object.entries(parsed).filter(([k]) => k !== "mode" && k !== "tool")
                  );
                }
              } catch {}
            }
          }

          const tcEntry = { tool, input: toolInput, result };

          if (last?.role === "assistant") {
            updated[lastIdx] = {
              ...last,
              toolCallsBefore: [...(last.toolCallsBefore || []), tcEntry],
              content: "", // Очищаем текст вызова после выполнения
            };
          }
          return updated;
        });

        // Прикрепляем tool-call к текущему assistant-сообщению и очищаем его контент
        // (следующий ответ модели будет новым текстом)
        // Обрабатываем present: привязываем файлы к конкретному сообщению
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
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
      />

      <div className="main-content">
        <Header
          models={models}
          selectedModel={selectedModel}
          isLoading={isLoading}
          onModelChange={handleModelChange}
          onOpenSandbox={() => setShowSandbox(true)}
          onOpenSettings={() => setShowSettings(true)}
        />

        {showSandbox && <SandboxManager onClose={() => setShowSandbox(false)} />}

        {showSettings && (
          <SettingsModal
            openrouterConfigured={openrouterConfigured}
            openrouterKeyInput={openrouterKeyInput}
            setOpenrouterKeyInput={setOpenrouterKeyInput}
            modelSettings={modelSettings}
            setModelSettings={setModelSettings}
            settingsSaving={settingsSaving}
            settingsError={settingsError}
            settingsSavedMsg={settingsSavedMsg}
            onSave={handleSaveSettings}
            onClose={() => setShowSettings(false)}
          />
        )}

        <main className="chat-container">
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
    </div>
  );
}
