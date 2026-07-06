from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from sandbox_manager import SandboxManager
from pydantic import BaseModel
import os
import shutil

router = APIRouter(prefix="/sandbox", tags=["sandbox"])

class FileContent(BaseModel):
    path: str
    content: str

@router.get("/files")
async def list_files(path: str = "/home/quadrogent"):
    """Список файлов в песочнице."""
    res = SandboxManager.run_command(f"ls -R -F {path}")
    if res.get("exit_code") != 0:
        raise HTTPException(status_code=500, detail=res.get("stderr") or res.get("error"))
    return {"output": res.get("stdout")}

@router.get("/read")
async def read_file(path: str):
    """Чтение файла из песочницы."""
    content = SandboxManager.read_file(path)
    return {"content": content}

@router.get("/download")
async def download_file(path: str):
    """Скачивание файла из песочницы."""
    try:
        content = SandboxManager.read_file(path)
        filename = os.path.basename(path)
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/write")
async def write_file(file: FileContent):
    """Запись файла в песочницу."""
    SandboxManager.write_file(file.path, file.content)
    return {"status": "ok"}

@router.post("/clear")
async def clear_sandbox():
    """Очистка рабочего пространства модели."""
    SandboxManager.run_command("rm -rf /home/quadrogent/*")
    SandboxManager.run_command("mkdir -p /home/quadrogent/uploads /home/quadrogent/output")
    return {"status": "ok"}

@router.delete("/delete")
async def delete_file(path: str):
    """Удаление файла или директории из песочницы."""
    try:
        res = SandboxManager.run_command(f"rm -rf {path}")
        if res.get("exit_code") != 0:
            raise HTTPException(status_code=500, detail=res.get("stderr") or "Ошибка удаления")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Загрузка файла в папку uploads песочницы."""
    try:
        # Создаем папку uploads если её нет
        SandboxManager.run_command("mkdir -p /home/quadrogent/uploads")
        
        # Путь внутри контейнера
        dest_path = f"/home/quadrogent/uploads/{file.filename}"
        
        # Читаем содержимое файла
        content = await file.read()
        
        # Записываем в песочницу
        # SandboxManager.write_file ожидает строку, для бинарных файлов используем docker cp или аналоги
        # Но для простоты сейчас используем текущий метод записи (текст)
        # Если нужно поддерживать бинарники, придется расширить SandboxManager
        SandboxManager.write_file(dest_path, content.decode('utf-8', errors='ignore'))
        
        return {"status": "ok", "filename": file.filename, "path": dest_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
