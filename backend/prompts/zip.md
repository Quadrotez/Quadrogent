## Tool: zip

**Description:** Create a zip archive of a specified file or directory.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "zip",
  "path": "<path_to_file_or_directory_to_archive>",
  "output_path": "<path_for_output_zip_file>"
}
```

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "zip",
  "path": "/home/quadrogent/my_project",
  "output_path": "/home/quadrogent/my_project.zip"
}
```

**Important:**
- `path` is the absolute path to the file or directory to be archived.
- `output_path` is the absolute path where the resulting `.zip` file will be saved.
