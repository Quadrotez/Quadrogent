## Tool: web_search

**Description:** Search the web using DuckDuckGo. Returns a list of results with title, URL, and snippet.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "web_search",
  "query": "<search query>",
  "max_results": 5
}
```

**Parameters:**
- `query` (required): The search query string.
- `max_results` (optional, default: 5): Maximum number of search results to return.

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "web_search",
  "query": "Python async programming best practices",
  "max_results": 3
}
```
