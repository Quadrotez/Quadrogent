import { useRef, useEffect } from "react";
import MarkdownMessage from "./MarkdownMessage";
import ToolCallBlock from "./ToolCallBlock";
import PresentedFiles from "./PresentedFiles";
import "./MessageList.css";

/**
 * Рендерит список сообщений.
 *
 * messages — массив { role, content, toolCalls? }
 *   toolCalls — массив { tool, input, result } встроенных вызовов инструментов
 *
 * isLoading, status — для индикатора набора текста
 * presentedFiles — файлы для блока "Презентованные файлы"
 */
export default function MessageList({ messages, isLoading, status, models, presentedFiles }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const getStatusText = () => {
    switch (status) {
      case "loading": return "Загрузка модели...";
      case "thinking": return "Думаю...";
      case "generating": return "Генерирую...";
      default: return "";
    }
  };

  return (
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

      {messages.map((msg, index) => {
        const hasTCs = msg.toolCallsBefore && msg.toolCallsBefore.length > 0;
        const isLastMsg = index === messages.length - 1;

        // Определяем финальный контент для assistant-сообщения
        // (MarkdownMessage вырезает JSON tool-calling, оставляя только chat-текст)
        let displayContent = msg.content;
        if (msg.role === "assistant" && msg.content) {
          // Проверяем, не является ли контент чистым JSON tool_calling (без текста)
          const jsonRegex = /\{[\s\S]*?\}/g;
          const stripped = msg.content.replace(jsonRegex, (match) => {
            try {
              const p = JSON.parse(match);
              if (p.mode === "tool_calling") return "";
              if (p.mode === "chat") return p.content || "";
              return match;
            } catch { return match; }
          }).trim();
          displayContent = stripped;
        }

        const hasText = !!displayContent;
        // Скрываем пустой пузырь если нет ни текста, ни tool-calls (кроме последнего загружаемого)
        if (!hasText && !hasTCs && !(msg.role === "assistant" && isLoading && isLastMsg)) {
          return null;
        }

        return (
          <div key={index} className={`message ${msg.role}`}>
            {/* Вызовы инструментов, встроенные ДО текста ответа */}
            {hasTCs && msg.toolCallsBefore.map((tc, ti) => (
              <ToolCallBlock
                key={`before-${ti}`}
                tool={tc.tool}
                input={tc.input}
                result={tc.result}
              />
            ))}

            {/* Текст сообщения — скрываем пузырь если текста нет */}
            {(hasText || (msg.role === "assistant" && isLoading && isLastMsg)) && (
              <div className="message-content">
                {hasText ? (
                  msg.role === "assistant" ? (
                    <MarkdownMessage content={msg.content} />
                  ) : (
                    msg.content
                  )
                ) : (
                  <span className="typing">●●●</span>
                )}
              </div>
            )}

            {/* Презентованные файлы привязываем к сообщению, в котором они появились */}
            {msg.role === "assistant" && msg.presentedFiles && msg.presentedFiles.length > 0 && (
              <PresentedFiles files={msg.presentedFiles} />
            )}

            {msg.role === "assistant" && isLoading && isLastMsg && status !== "idle" && (
              <div className="status-indicator">
                <span className="status-dot"></span>
                {getStatusText()}
              </div>
            )}
          </div>
        );
      })}

      <div ref={endRef} />
    </div>
  );
}
