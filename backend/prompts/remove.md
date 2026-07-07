## Tool: remove

**Description:** Remove files or directories from the sandbox environment.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "remove",
  "path": "<path_to_remove>"
}
```

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "remove",
  "path": "/home/quadrogent/old_file.txt"
}
```

**Important:**
- `path` is the absolute path to the file or directory to be removed.
- This command uses `rm -rf`, so use with caution as it will forcefully remove files and directories recursively without confirmation.
