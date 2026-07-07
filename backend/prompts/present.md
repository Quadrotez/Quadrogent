## Tool: present

**Description:** Present a file or directory to the user for download. This copies the specified path into the `/home/quadrogent/output` directory, making it available for the user to download via the frontend.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "present",
  "path": "<path_to_file_or_directory>"
}
```

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "present",
  "path": "/home/quadrogent/output/report.pdf"
}
```

**Important:**
- `path` is the absolute path to the file or directory to be presented.
- If a directory is presented, it will be copied recursively.
- The tool will return the full path to the presented item in the `/home/quadrogent/output` directory.
