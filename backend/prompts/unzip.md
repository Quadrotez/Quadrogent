## Tool: unzip

**Description:** Extract files from a zip archive to a specified directory.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "unzip",
  "path": "<path_to_zip_file>",
  "output_path": "<path_for_extraction>"
}
```

**Example:**
```json
{
  "mode": "tool_calling",
  "tool": "unzip",
  "path": "/home/quadrogent/my_project.zip",
  "output_path": "/home/quadrogent/extracted_project"
}
```

**Important:**
- `path` is the absolute path to the `.zip` file to be extracted.
- `output_path` is the absolute path to the directory where the contents will be extracted.
