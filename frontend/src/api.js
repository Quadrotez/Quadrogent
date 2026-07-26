const API_BASE = "/api";

export async function fetchModels() {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) throw new Error(`Ошибка загрузки моделей: ${res.status}`);
  const data = await res.json();
  return { models: data.models || [], errors: data.errors || null };
}

export async function fetchRunningModels() {
  const res = await fetch(`${API_BASE}/models/running`);
  if (!res.ok) throw new Error(`Ошибка: ${res.status}`);
  const data = await res.json();
  return data.models || [];
}

export async function fetchSettings() {
  const res = await fetch(`${API_BASE}/settings`);
  if (!res.ok) throw new Error(`Ошибка загрузки настроек: ${res.status}`);
  return res.json();
}

export async function fetchProviders() {
  const res = await fetch(`${API_BASE}/settings/providers`);
  if (!res.ok) throw new Error(`Ошибка загрузки провайдеров: ${res.status}`);
  const data = await res.json();
  return data.providers || [];
}

export async function saveApiKey(provider, apiKey, baseUrl, proxyUrl, enabled) {
  const res = await fetch(`${API_BASE}/settings/api-key`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider,
      api_key: apiKey || null,
      base_url: baseUrl || null,
      proxy_url: proxyUrl || null,
      enabled: enabled !== undefined ? enabled : undefined,
    }),
  });
  if (!res.ok) throw new Error(`Ошибка сохранения ключа: ${res.status}`);
  return res.json();
}

export async function testProvider(name) {
  const res = await fetch(`${API_BASE}/settings/providers/${name}/test`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Ошибка тестирования: ${res.status}`);
  return res.json();
}

export async function saveSetting(key, value) {
  const res = await fetch(`${API_BASE}/settings/setting`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, value: String(value) }),
  });
  if (!res.ok) throw new Error(`Ошибка сохранения настройки: ${res.status}`);
  return res.json();
}

// --- История чатов ---
export async function fetchChats() {
  const res = await fetch(`${API_BASE}/chats`);
  if (!res.ok) throw new Error(`Ошибка загрузки чатов: ${res.status}`);
  const data = await res.json();
  return data.chats || [];
}

export async function fetchChat(chatId) {
  const res = await fetch(`${API_BASE}/chats/${chatId}`);
  if (!res.ok) throw new Error(`Ошибка загрузки чата: ${res.status}`);
  return res.json();
}

export async function deleteChat(chatId) {
  const res = await fetch(`${API_BASE}/chats/${chatId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Ошибка удаления чата: ${res.status}`);
  return res.json();
}

export async function streamChat(model, messages, onChunk, onDone, onError, signal, chatId = null, onChatId = null, onToolResult = null, onTitle = null, onToolExecuting = null) {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, messages, chat_id: chatId }),
      signal,
    });

    if (!res.ok) {
      // Обработка 429 Rate Limit
      if (res.status === 429) {
        try {
          const errorData = await res.json();
          const retryAfter = errorData.metadata?.retry_after_seconds || errorData.retry_after_seconds;
          if (retryAfter) {
            const waitTime = (parseFloat(retryAfter) + 1) * 1000;
            onChunk(`\n\n*Система: Превышен лимит запросов. Повторная попытка через ${Math.round(waitTime/1000)} сек...*\n\n`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
            return streamChat(model, messages, onChunk, onDone, onError, signal, chatId, onChatId, onToolResult, null, onToolExecuting);
          }
        } catch (e) {
          console.error("Не удалось распарсить ошибку 429", e);
        }
      }
      throw new Error(`Ошибка API: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value, { stream: true });
      buffer += text;

      const events = buffer.split("\n\n");
      buffer = events.pop();

      for (const event of events) {
        if (!event.trim()) continue;

        const lines = event.split("\n");
        let isErrorEvent = false;
        let isChatIdEvent = false;
        let isToolResultEvent = false;
        let isToolExecutingEvent = false;
        let isTitleEvent = false;

        for (const line of lines) {
          if (line.trim() === "event: error") isErrorEvent = true;
          if (line.trim() === "event: chat_id") isChatIdEvent = true;
          if (line.trim() === "event: tool_result") isToolResultEvent = true;
          if (line.trim() === "event: tool_executing") isToolExecutingEvent = true;
          if (line.trim() === "event: title") isTitleEvent = true;
        }

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;

          let payload = line.slice(5);
          if (payload.startsWith(" ")) {
            payload = payload.slice(1);
          }
          payload = payload.trim();

          if (isChatIdEvent) {
            if (onChatId) onChatId(parseInt(payload, 10));
            continue;
          }

          if (isErrorEvent) {
            onError(payload || "Неизвестная ошибка");
            return;
          }

          if (isToolResultEvent) {
            if (onToolResult) {
                try {
                    onToolResult(JSON.parse(payload));
                } catch (e) {
                    console.error("Error parsing tool_result payload:", e);
                }
            }
            continue;
          }

          if (isToolExecutingEvent) {
            if (onToolExecuting) {
                try {
                    onToolExecuting(JSON.parse(payload));
                } catch (e) {
                    console.error("Error parsing tool_executing payload:", e);
                }
            }
            continue;
          }

          if (isTitleEvent) {
            if (onTitle) {
              try {
                onTitle(JSON.parse(payload));
              } catch (e) {
                onTitle(payload);
              }
            }
            continue;
          }

          if (payload === "[DONE]") {
            onDone();
            return;
          }
          if (payload === "") continue;

          let text;
          try {
            const parsed = JSON.parse(payload);
            if (parsed && typeof parsed === "object") {
              if (parsed.type === "retry_note") {
                text = parsed.content || "";
              } else if (parsed.type === "error") {
                onError(parsed.content || "Неизвестная ошибка");
                return;
              } else {
                text = JSON.stringify(parsed);
              }
            } else {
              text = parsed;
            }
          } catch {
            text = payload;
          }

          if (text !== "") {
            onChunk(text);
          }
        }
      }
    }

    onDone();
  } catch (err) {
    if (err.name === "AbortError") {
      onDone();
      return;
    }
    onError(err.message || "Неизвестная ошибка");
  }
}

// --- Sandbox API ---
export async function fetchSandboxFiles(path) {
  const res = await fetch(`${API_BASE}/sandbox/files?path=${encodeURIComponent(path || "/home/quadrogent")}`);
  if (!res.ok) throw new Error(`Ошибка загрузки файлов: ${res.status}`);
  return res.json(); // { path, entries: [{name, path, type}] }
}

export async function deleteSandboxFile(path) {
  const res = await fetch(`${API_BASE}/sandbox/delete?path=${encodeURIComponent(path)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Ошибка удаления: ${res.status}`);
  return res.json();
}

export async function readSandboxFile(path) {
  const res = await fetch(`${API_BASE}/sandbox/read?path=${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error(`Ошибка чтения файла: ${res.status}`);
  return res.json();
}

export async function writeSandboxFile(path, content) {
  const res = await fetch(`${API_BASE}/sandbox/write`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, content }),
  });
  if (!res.ok) throw new Error(`Ошибка записи файла: ${res.status}`);
  return res.json();
}

export async function clearSandbox() {
  const res = await fetch(`${API_BASE}/sandbox/clear`, { method: "POST" });
  if (!res.ok) throw new Error(`Ошибка очистки песочницы: ${res.status}`);
  return res.json();
}