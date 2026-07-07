## Tool: patch_file

**Description:** Overwrite the content of an existing file in the sandbox environment. This is functionally identical to `create_file` but semantically implies modifying an existing file.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "patch_file",
  "path": "<path_to_file>",
  "content": "<new_file_content>"
}
```

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "patch_file",
  "path": "/home/quadrogent/my_script.py",
  "content": "print(\'Updated script!\')"
}
```

**Important:**
- `path` is the absolute path to the file to be modified.
- `content` can be a single string or an **array of strings** (recommended for large files). If it's an array, lines will be joined with newlines automatically.

**Example with Array:**
```json
{
  "mode": "tool_calling",
  "tool": "patch_file",
  "path": "/home/quadrogent/style.css",
  "content": [
    "body { background: red; }",
    "h1 { color: blue; }"
  ]
}
```
