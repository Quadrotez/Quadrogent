## Tool: present

**Description:** Make a file or directory available for the user to download. 

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "present",
  "path": "<path_to_file_or_directory>"
}
```

**Important:**
- If you provide a **directory** path, the system will **automatically pack it into a ZIP archive** before presenting it to the user.
- The user will see the file in the "Presented Files" section of the UI.
- Use this when you have finished creating a project, generated a report, or want to share any result files.

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "present",
  "path": "/home/quadrogent/my_project"
}
```
*(Result: user receives `my_project.zip`)*
