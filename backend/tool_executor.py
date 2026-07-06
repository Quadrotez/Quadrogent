import json
import logging
import os
from sandbox_manager import SandboxManager

logger = logging.getLogger("quadrogent.tools")

class ToolExecutor:
    @staticmethod
    async def execute(tool_name: str, args: dict):
        logger.info(f"Выполнение инструмента: {tool_name} с аргументами {args}")
        
        if tool_name == "bash":
            return SandboxManager.run_command(args.get("content", ""))
        
        elif tool_name == "create_file":
            path = args.get("path")
            content_raw = args.get("content", "")
            if not path:
                return {"error": "Путь обязателен", "exit_code": 1}
            
            if isinstance(content_raw, list):
                content = "\n".join(content_raw)
            else:
                content = str(content_raw)
                
            SandboxManager.write_file(path, content)
            return {"stdout": f"Файл успешно создан: {path}", "exit_code": 0}
            
        elif tool_name == "patch_file":
            path = args.get("path")
            content_raw = args.get("content", "")
            if not path:
                return {"error": "Путь обязателен", "exit_code": 1}
            
            if isinstance(content_raw, list):
                content = "\n".join(content_raw)
            else:
                content = str(content_raw)
                
            SandboxManager.write_file(path, content)
            return {"stdout": f"Файл успешно изменён: {path}", "exit_code": 0}
            
        elif tool_name == "remove":
            path = args.get("path")
            if not path:
                return {"error": "Path is required", "exit_code": 1}
            return SandboxManager.run_command(f"rm -rf {path}")
            
        elif tool_name == "makedir":
            path = args.get("path")
            if not path:
                return {"error": "Path is required", "exit_code": 1}
            return SandboxManager.run_command(f"mkdir -p {path}")
            
        elif tool_name == "install":
            pkg_type = args.get("type")
            package = args.get("package")
            venv = args.get("virtualenv")
            
            if pkg_type == "apt":
                return SandboxManager.run_command(f"sudo apt-get install -y {package}")
            elif pkg_type == "pip":
                pip_cmd = f"{venv}/bin/pip" if venv else "pip"
                return SandboxManager.run_command(f"{pip_cmd} install {package}")
            return {"error": f"Unknown install type: {pkg_type}", "exit_code": 1}
            
        elif tool_name == "present":
            path = args.get("path")
            if not path:
                return {"error": "Путь обязателен", "exit_code": 1}
            
            # Убеждаемся, что директория output существует
            SandboxManager.run_command("mkdir -p /home/quadrogent/output")
            
            filename = os.path.basename(path)
            dest = f"/home/quadrogent/output/{filename}"
            
            # Сначала убираем возможный старый файл/папку с таким же именем в output.
            # Без этого `cp -r` для директорий не заменяет старое содержимое, а
            # вкладывает новую папку внутрь старой, из-за чего в output остаются
            # файлы, которые не презентовались текущим вызовом present.
            SandboxManager.run_command(f"rm -rf {dest}")
            
            # Используем cp для презентации
            res = SandboxManager.run_command(f"cp -r {path} {dest}")
            if res.get("exit_code") == 0:
                # Возвращаем путь относительно корня песочницы для фронтенда
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
            
        return {"error": f"Unknown tool: {tool_name}", "exit_code": 1}
