from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from sandbox_manager import SandboxManager
from pydantic import BaseModel
import os

router = APIRouter(prefix="/sandbox", tags=["sandbox"])

class FileContent(BaseModel):
    path: str
    content: str

@router.get("/files")
async def list_files(path: str = "/home/quadrogent"):
    res = await SandboxManager.run_command(f"ls -1 -p {path} 2>&1")
    if res.get("exit_code") != 0:
        raise HTTPException(status_code=500, detail=res.get("stderr") or res.get("error") or "Ошибка листинга")

    stdout = res.get("stdout", "")
    entries = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line in (".", ".."):
            continue
        is_dir = line.endswith("/")
        name = line.rstrip("/")
        full_path = path.rstrip("/") + "/" + name
        entries.append({
            "name": name,
            "path": full_path,
            "type": "dir" if is_dir else "file",
        })

    return {"path": path, "entries": entries}

@router.get("/read")
async def read_file(path: str):
    try:
        content = SandboxManager.read_file(path)
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download")
async def download_file(path: str):
    try:
        content = SandboxManager.read_file_binary(path)
        filename = os.path.basename(path)
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/write")
async def write_file(file: FileContent):
    await SandboxManager.write_file(file.path, file.content)
    return {"status": "ok"}

@router.post("/clear")
async def clear_sandbox():
    await SandboxManager.run_command("rm -rf /home/quadrogent/*")
    await SandboxManager.run_command("mkdir -p /home/quadrogent/uploads /home/quadrogent/output")
    return {"status": "ok"}

@router.delete("/delete")
async def delete_file(path: str):
    try:
        res = await SandboxManager.run_command(f"rm -rf {path}")
        if res.get("exit_code") != 0:
            raise HTTPException(status_code=500, detail=res.get("stderr") or "Ошибка удаления")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        await SandboxManager.run_command("mkdir -p /home/quadrogent/uploads")
        dest_path = f"/home/quadrogent/uploads/{file.filename}"
        content = await file.read()
        await SandboxManager.write_file_binary(dest_path, content)
        return {"status": "ok", "filename": file.filename, "path": dest_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
