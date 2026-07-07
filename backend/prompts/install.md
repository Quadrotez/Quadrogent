## Tool: install

**Description:** Install packages in the sandbox environment using `apk` (for system packages) or `pip` (for Python packages).

**Usage:**
```json
{
  "mode": "tool_calling",
  "tool": "install",
  "type": "<package_manager_type>",
  "package": "<package_name>",
  "update": true,
  "virtualenv": "<path_to_virtualenv>" (optional, for pip)
}
```

**Example (apk with update):**
```json
{
  "mode": "tool_calling",
  "tool": "install",
  "type": "apk",
  "package": "git",
  "update": true
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
- `type` can be `apk` or `pip`.
- `package` is the name of the package to install.
- `update` is optional (default: false). If true, it runs `apk update` before installation. Only relevant for `type: apk`.
- `virtualenv` is optional and specifies the path to a Python virtual environment for `pip` installations.
