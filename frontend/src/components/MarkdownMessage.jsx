import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import "katex/dist/katex.min.css";
import "highlight.js/styles/github-dark.css";

export default function MarkdownMessage({ content }) {
  // Ищем все JSON объекты в тексте сообщения
  let finalContent = content;

  // Если контент содержит JSON в markdown-блоке, извлекаем его
  const markdownJsonMatch = content.match(/```(?:json)?\n([\s\S]*?)\n```/);
  if (markdownJsonMatch) {
    try {
      const parsed = JSON.parse(markdownJsonMatch[1]);
      if (parsed.mode === "chat") {
        const chatText = Array.isArray(parsed.content)
          ? parsed.content.join("\n")
          : parsed.content || "";
        // Заменяем весь markdown-блок на извлеченный текст чата
        finalContent = content.replace(markdownJsonMatch[0], chatText);
      } else if (parsed.mode === "tool_calling") {
        // Если это tool_calling, удаляем весь markdown-блок
        finalContent = content.replace(markdownJsonMatch[0], "");
      }
    } catch (e) {
      // Если невалидный JSON, оставляем как есть
    }
  }

  // Также обрабатываем старый формат, где JSON мог быть без markdown-блока
  const jsonRegex = /\{[\s\S]*?\}/g;
  let chatContentFromOldFormat = "";
  finalContent = finalContent.replace(jsonRegex, (match) => {
    try {
      const parsed = JSON.parse(match);
      if (parsed.mode === "chat") {
        const c = Array.isArray(parsed.content)
          ? parsed.content.join("\n")
          : parsed.content || "";
        chatContentFromOldFormat += c + "\n";
      }
      return ""; // Вырезаем все JSON из основного текста
    } catch (e) {
      return match; // Если не JSON, оставляем как есть
    }
  }).trim();

  finalContent = (finalContent + "\n" + chatContentFromOldFormat).trim();

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeHighlight, rehypeKatex]}
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
