## Tool: makedir

**Description:** Create a new directory in the sandbox environment.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "makedir",
  "path": "<path_to_directory>"
}
```

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "makedir",
  "path": "/home/quadrogent/new_project"
}
```

**Important:**
- `path` is the absolute path for the new directory.
- This command uses `mkdir -p`, so it will create parent directories as needed and will not return an error if the directory already exists.
