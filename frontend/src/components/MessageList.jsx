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
export default function MessageList({ messages, isLoading, status, models }) {
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
        let displayContent = msg.content || "";

        const hasText = !!displayContent;
        const hasFiles = msg.presentedFiles && msg.presentedFiles.length > 0;
        const isLastAndStillGenerating = msg.role === "assistant" && isLoading && isLastMsg;
        const hasRawContent = msg.role === "assistant" && !!msg.content;
        if (!hasText && !hasTCs && !hasFiles && !isLastAndStillGenerating && !hasRawContent) {
          return null;
        }

        return (
          <div key={index} className={`message ${msg.role}`}>
            {/* Вызовы инструментов — ПЕРЕД текстом (порядок выполнения: инструменты потом текст) */}
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
