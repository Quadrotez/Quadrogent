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
