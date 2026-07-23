## Tool: web_fetch

**Description:** Fetch the content of a web page by URL. Returns the raw text content (HTML, JSON, XML, etc.).

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "web_fetch",
  "url": "<full_url>"
}
```

**Parameters:**
- `url` (required): The full URL to fetch (must include protocol, e.g. `https://example.com`).

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "web_fetch",
  "url": "https://example.com"
}
```

**Important:**
- The response follows redirects automatically.
- Binary content (images, archives, etc.) is detected and not included in the output.
