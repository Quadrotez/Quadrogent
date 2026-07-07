## Tool: install

**Description:** Install packages in the sandbox environment using `apt` or `pip`.

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "install",
  "type": "<package_manager_type>",
  "package": "<package_name>",
  "virtualenv": "<path_to_virtualenv>" (optional, for pip)
}
```

**Example (apt):**
```json
{
  "mode": "tool_calling",
  "tool": "install",
  "type": "apt",
  "package": "git"
}
```

**Example (pip):**
```json
{
  "mode": "tool_calling",
  "tool": "install",
  "type": "pip",
  "package": "requests",
  "virtualenv": "/home/quadrogent/my_venv"
}
```

**Important:**
- `type` can be `apt` or `pip`.
- `package` is the name of the package to install.
- `virtualenv` is optional and specifies the path to a Python virtual environment for `pip` installations.
