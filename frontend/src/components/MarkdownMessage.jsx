import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import { parseThinkTags } from "../utils/thinkTag";
import "katex/dist/katex.min.css";
import "highlight.js/styles/github-dark.css";
import "./MarkdownMessage.css";

function ThinkingBlock({ content, complete }) {
  return (
    <details className="thinking-block">
      <summary className="thinking-summary">
        <span className="thinking-icon">
          {complete ? "💭" : "⏳"}
        </span>
        {complete ? "В раздумье…" : "Думаю…"}
      </summary>
      <div className="thinking-content">
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeHighlight, rehypeKatex]}
        >
          {content}
        </ReactMarkdown>
      </div>
    </details>
  );
}

function MarkdownBlock({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeHighlight, rehypeKatex]}
      components={{
        a: ({ node: _node, ...props }) => (
          <a {...props} target="_blank" rel="noopener noreferrer" />
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

export default function MarkdownMessage({ content }) {
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
        finalContent = content.replace(markdownJsonMatch[0], chatText);
      } else if (parsed.mode === "tool_calling") {
        finalContent = content.replace(markdownJsonMatch[0], "");
      }
    } catch {
      // Если невалидный JSON, оставляем как есть
    }
  }

  // Обработка старого формата JSON без markdown-блока
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
      return "";
    } catch {
      return match;
    }
  }).trim();

  finalContent = (finalContent + "\n" + chatContentFromOldFormat).trim();

  // Парсим think-теги
  const { segments, hasThinking } = useMemo(
    () => parseThinkTags(finalContent),
    [finalContent]
  );

  if (!hasThinking) {
    return <MarkdownBlock content={finalContent} />;
  }

  return (
    <div className="markdown-with-thinking">
      {segments.map((seg, i) => {
        if (seg.type === "thinking") {
          return (
            <ThinkingBlock
              key={`think-${i}`}
              content={seg.content}
              complete={seg.complete}
            />
          );
        }
        if (!seg.content.trim()) return null;
        return <MarkdownBlock key={`text-${i}`} content={seg.content} />;
      })}
    </div>
  );
}
