import json
import logging
import os
from sandbox_manager import SandboxManager

logger = logging.getLogger("quadrogent.tools")

class ToolExecutor:
    # Схемы валидации для инструментов
    SCHEMAS = {
        "bash": {"required": ["command"], "optional": ["mode", "tool"]},
        "create_file": {"required": ["path", "content"], "optional": ["mode", "tool"]},
        "patch_file": {"required": ["path", "content"], "optional": ["mode", "tool"]},
        "remove": {"required": ["path"], "optional": ["mode", "tool"]},
        "makedir": {"required": ["path"], "optional": ["mode", "tool"]},
        "install": {"required": ["type", "package"], "optional": ["mode", "tool", "update", "virtualenv"]},
        "present": {"required": ["path"], "optional": ["mode", "tool"]},
        "zip": {"required": ["path", "output_path"], "optional": ["mode", "tool"]},
        "unzip": {"required": ["path", "output_path"], "optional": ["mode", "tool"]},
        "stop": {"required": [], "optional": ["mode", "tool"]},
        "read_skill": {"required": ["name"], "optional": ["mode", "tool"]}
    }

    @staticmethod
    def get_skill_content(skill_name: str):
        """Вспомогательный метод для чтения контента скилла."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompts_dir = os.path.join(current_dir, "prompts")
        skill_path = os.path.join(prompts_dir, f"{skill_name}.md")
        
        if os.path.exists(skill_path):
            try:
                with open(skill_path, "r", encoding="utf-8") as f:
                    return f.read()
            except:
                return None
        return None

    @staticmethod
    async def execute(tool_name: str, args: dict, read_skills: set = None):
        logger.info(f"Выполнение инструмента: {tool_name} с аргументами {args}")
        
        # 1. Валидация аргументов
        if tool_name in ToolExecutor.SCHEMAS:
            schema = ToolExecutor.SCHEMAS[tool_name]
            missing = [field for field in schema["required"] if field not in args]
            
            # Проверка на лишние поля (исключая служебные mode и tool)
            allowed = set(schema["required"]) | set(schema["optional"])
            extra = [field for field in args if field not in allowed]
            
            if missing or extra:
                error_msg = f"Ошибка валидации инструмента '{tool_name}':\n"
                if missing:
                    error_msg += f"- Отсутствуют обязательные поля: {', '.join(missing)}\n"
                if extra:
                    error_msg += f"- Обнаружены лишние или неизвестные поля: {', '.join(extra)}\n"
                
                # Если модель не читала этот скилл, прикладываем его
                if read_skills is not None and tool_name not in read_skills:
                    skill_content = ToolExecutor.get_skill_content(tool_name)
                    if skill_content:
                        error_msg += f"\nПохоже, ты не читал документацию этого инструмента. Вот она:\n\n{skill_content}"
                
                return {"error": error_msg, "exit_code": 1}

        # 2. Исполнение
        if tool_name == "bash":
            return SandboxManager.run_command(args.get("command", ""))
        
        elif tool_name == "create_file":
            path = args.get("path")
            content_raw = args.get("content", "")
            
            if isinstance(content_raw, list):
                content = "\n".join([str(line) for line in content_raw])
            else:
                content = str(content_raw)
                
            SandboxManager.write_file(path, content)
            return {"stdout": f"Файл успешно создан: {path}", "exit_code": 0}
            
        elif tool_name == "patch_file":
            path = args.get("path")
            content_raw = args.get("content", "")
            
            if isinstance(content_raw, list):
                content = "\n".join([str(line) for line in content_raw])
            else:
                content = str(content_raw)
                
            SandboxManager.write_file(path, content)
            return {"stdout": f"Файл успешно изменён: {path}", "exit_code": 0}
            
        elif tool_name == "remove":
            path = args.get("path")
            return SandboxManager.run_command(f"rm -rf {path}")
            
        elif tool_name == "makedir":
            path = args.get("path")
            return SandboxManager.run_command(f"mkdir -p {path}")
            
        elif tool_name == "install":
            pkg_type = args.get("type")
            package = args.get("package")
            venv = args.get("virtualenv")
            should_update = args.get("update", False)
            
            if pkg_type == "apk":
                update_cmd = "apk update && " if should_update else ""
                cmd = f"{update_cmd}apk add --no-cache {package}"
                return SandboxManager.run_command(cmd, user="root")
            elif pkg_type == "pip":
                pip_cmd = f"{venv}/bin/pip" if venv else "pip"
                return SandboxManager.run_command(f"{pip_cmd} install {package}")
            return {"error": f"Unknown install type: {pkg_type}", "exit_code": 1}
            
        elif tool_name == "present":
            path = args.get("path")
            SandboxManager.run_command("mkdir -p /home/quadrogent/output")
            
            # Проверяем, является ли путь директорией
            check_dir = SandboxManager.run_command(f"test -d {path}")
            is_dir = check_dir.get("exit_code") == 0
            
            filename = os.path.basename(path.rstrip("/"))
            
            if is_dir:
                # Если директория — пакуем в zip
                zip_filename = f"{filename}.zip"
                dest = f"/home/quadrogent/output/{zip_filename}"
                SandboxManager.run_command(f"rm -rf {dest}")
                # Переходим в родительскую папку, чтобы в архиве не было лишних путей
                parent_dir = os.path.dirname(path.rstrip("/")) or "."
                base_name = os.path.basename(path.rstrip("/"))
                res = SandboxManager.run_command(f"cd {parent_dir} && zip -r {dest} {base_name}")
            else:
                # Если файл — просто копируем
                dest = f"/home/quadrogent/output/{filename}"
                SandboxManager.run_command(f"rm -rf {dest}")
                res = SandboxManager.run_command(f"cp {path} {dest}")
                
            if res.get("exit_code") == 0:
                return {"stdout": f"Презентовано: {dest}", "exit_code": 0}
            return res
            
        elif tool_name == "zip":
            path = args.get("path")
            output_path = args.get("output_path")
            return SandboxManager.run_command(f"zip -r {output_path} {path}")
            
        elif tool_name == "unzip":
            path = args.get("path")
            output_path = args.get("output_path")
            return SandboxManager.run_command(f"unzip {path} -d {output_path}")
            
        elif tool_name == "stop":
            return {"stdout": "Работа завершена", "exit_code": 0, "stop": True}
            
        elif tool_name == "read_skill":
            skill_name = args.get("name")
            content = ToolExecutor.get_skill_content(skill_name)
            if content:
                return {"stdout": content, "exit_code": 0}
            else:
                return {"error": f"Skill '{skill_name}' not found", "exit_code": 1}
            
        res = {"error": f"Unknown tool: {tool_name}", "exit_code": 1}
        return res

    @staticmethod
    def wrap_result(result: dict):
        """Добавляет системное напоминание к результату инструмента."""
        reminder = "\n\n--- SYSTEM REMINDER ---\nAlways wrap your tool calls in ```json ... ``` blocks. Ensure the JSON is valid and complete. If you need to perform a new action, call 'read_skill' first if you haven't read that skill in this session."
        if "stdout" in result:
            result["stdout"] = str(result["stdout"]) + reminder
        elif "error" in result:
            result["error"] = str(result["error"]) + reminder
        else:
            result["stdout"] = reminder
        return result
