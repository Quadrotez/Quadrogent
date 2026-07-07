import "./ToolCallBlock.css";

/**
 * Отображает один вызов инструмента в потоке сообщений.
 *
 * Props:
 *   tool   — имя инструмента (строка)
 *   input  — параметры вызова (объект или строка JSON)
 *   result — результат выполнения (объект { exit_code, stdout, stderr, error }) или null, если ещё выполняется
 */
export default function ToolCallBlock({ tool, input, result }) {
  const isPending = result === null || result === undefined;
  const isSuccess = !isPending && result.exit_code === 0;

  // Парсим input: может быть строкой JSON или уже объектом
  let parsedInput = input;
  if (typeof input === "string") {
    try {
      parsedInput = JSON.parse(input);
    } catch {
      parsedInput = { raw: input };
    }
  }

  // Убираем служебные поля mode/tool из отображения параметров
  const displayParams = parsedInput
    ? Object.fromEntries(
        Object.entries(parsedInput).filter(
          ([k]) => k !== "mode" && k !== "tool"
        )
      )
    : null;

  const hasParams = displayParams && Object.keys(displayParams).length > 0;

  return (
    <div className={`tool-call-block ${isPending ? "pending" : isSuccess ? "success" : "error"}`}>
      <details>
        <summary className="tool-call-summary">
          <span className="tool-call-status-icon">
            {isPending ? "⏳" : isSuccess ? "✅" : "❌"}
          </span>
          <span className="tool-call-name">
            {tool === "read_skill" ? "📖 Изучение скилла: " : "🛠️ Инструмент: "}
            <strong>{tool === "read_skill" ? (displayParams?.name || tool) : tool}</strong>
          </span>
          <span className="tool-call-badge">
            {isPending ? "Выполняется…" : isSuccess ? "Успешно" : "Ошибка"}
          </span>
        </summary>

        <div className="tool-call-body">
          <div className="tool-call-grid">
            {/* Секция Запроса */}
            <div className="tool-call-section">
              <div className="tool-call-section-label">Запрос:</div>
              <pre className="tool-call-pre tool-call-input">
                {hasParams ? JSON.stringify(displayParams, null, 2) : "Нет параметров"}
              </pre>
            </div>

            {/* Секция Результата */}
            {!isPending && (
              <div className="tool-call-section">
                <div className="tool-call-section-label">Результат:</div>
                <div className="tool-call-result-container">
                  {result.stdout && (
                    <pre className="tool-call-pre tool-call-stdout">
                      {result.stdout}
                    </pre>
                  )}
                  {result.stderr && (
                    <>
                      <div className="tool-call-section-label tool-call-section-label--error">
                        Stderr:
                      </div>
                      <pre className="tool-call-pre tool-call-stderr">
                        {result.stderr}
                      </pre>
                    </>
                  )}
                  {result.error && (
                    <>
                      <div className="tool-call-section-label tool-call-section-label--error">
                        Ошибка:
                      </div>
                      <pre className="tool-call-pre tool-call-stderr">
                        {result.error}
                      </pre>
                    </>
                  )}
                  {!result.stdout && !result.stderr && !result.error && (
                    <div className="tool-call-empty-result">Пустой вывод</div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </details>
    </div>
  );
}
