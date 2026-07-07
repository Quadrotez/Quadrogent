## Tool: create_file

**Description:** Create a new file with specified content in the sandbox environment. If the file already exists, its content will be overwritten.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "create_file",
  "path": "<path_to_file>",
  "content": "<file_content>"
}
```

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "create_file",
  "path": "/home/quadrogent/my_script.py",
  "content": "print('Hello from sandbox!')"
}
```

**Important:**
- `path` is the absolute path where the file will be created.
- `content` can be a single string or an **array of strings** (recommended for large files). If it's an array, lines will be joined with newlines automatically.

**Example with Array:**
```json
{
  "mode": "tool_calling",
  "tool": "create_file",
  "path": "/home/quadrogent/index.html",
  "content": [
    "<!DOCTYPE html>",
    "<html>",
    "<body>Hello</body>",
    "</html>"
  ]
}
```
