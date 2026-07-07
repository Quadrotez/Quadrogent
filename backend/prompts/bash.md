## Tool: bash

**Description:** Execute shell commands in the sandbox environment.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "bash",
  "command": "<your_shell_command>"
}
```

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "bash",
  "command": "ls -la"
}
```

**Important:**
- The command will be executed in a Linux shell.
- Avoid interactive commands.
- Use `2>&1` to redirect stderr to stdout for easier parsing of results.
- If the command is long or complex, consider writing it to a file and then executing the file.
