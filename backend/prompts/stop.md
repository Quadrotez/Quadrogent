## Tool: stop

**Description:** Signal the completion of the current task or a logical stopping point in a multi-step process. This tool is used when the model believes it has achieved the user's request or reached a state where further action is not immediately required.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "stop"
}
```

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "stop"
}
```

**Important:**
- This tool does not require any parameters.
- Use this tool when you have completed the user's request and no further actions are needed from you.
