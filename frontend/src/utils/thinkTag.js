/**
 * Парсит блоки <think>text</think> из контента сообщения.
 *
 * Возвращает { segments, hasThinking } где segments — массив объектов:
 *   { type: "thinking" | "text", content: string }
 *
 * Поддерживает незавершённые блоки (во время стриминга),
 * когда <think> уже получен, а  ещё нет.
 */
export function parseThinkTags(content) {
  if (!content) return { segments: [{ type: "text", content: "" }], hasThinking: false };

  const segments = [];
  let hasThinking = false;

  // Regex: ловим завершённые блоки и незавершённый (если стриминг)
  // Завершённый: <think>...</think>
  // Незавершённый (стриминг): <think>... (без закрывающего тега до конца строки)
  const thinkRegex = /<think>([\s\S]*?)(?:<\/think>|$)/g;
  let lastIndex = 0;
  let match;

  while ((match = thinkRegex.exec(content)) !== null) {
    // Текст перед блоком
    if (match.index > lastIndex) {
      segments.push({ type: "text", content: content.slice(lastIndex, match.index) });
    }

    const thinkContent = match[1];
    const isComplete = match[0].endsWith("</think>");
    hasThinking = true;

    segments.push({
      type: "thinking",
      content: thinkContent,
      complete: isComplete,
    });

    lastIndex = match.index + match[0].length;
  }

  // Остаток после последнего блока
  if (lastIndex < content.length) {
    segments.push({ type: "text", content: content.slice(lastIndex) });
  }

  // Если ничего не нашли — весь контент как текст
  if (segments.length === 0) {
    segments.push({ type: "text", content });
  }

  return { segments, hasThinking };
}
