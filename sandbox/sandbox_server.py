import os
import base64
import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Quadrogent Sandbox API")

HOME = os.getenv("HOME", "/home/quadrogent")


class ExecRequest(BaseModel):
    command: str
    timeout: int = 60
    user: str = "quadrogent"


class WriteRequest(BaseModel):
    path: str
    content: str


class WriteBinaryRequest(BaseModel):
    path: str
    content: str  # base64


@app.post("/exec")
def exec_command(req: ExecRequest):
    full_cmd = ["bash", "-c", req.command]
    try:
        result = subprocess.run(
            full_cmd, capture_output=True, text=True,
            timeout=req.timeout, cwd=HOME,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timeout expired", "exit_code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1}


@app.post("/write")
def write_file(req: WriteRequest):
    parent = os.path.dirname(req.path)
    if parent and parent != "/":
        os.makedirs(parent, exist_ok=True)
    with open(req.path, "w", encoding="utf-8") as f:
        f.write(req.content)
    return {"status": "ok"}


@app.post("/write-binary")
def write_file_binary(req: WriteBinaryRequest):
    parent = os.path.dirname(req.path)
    if parent and parent != "/":
        os.makedirs(parent, exist_ok=True)
    with open(req.path, "wb") as f:
        f.write(base64.b64decode(req.content))
    return {"status": "ok"}


@app.get("/read")
def read_file(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    with open(path, "r", encoding="utf-8") as f:
        return {"content": f.read()}


@app.get("/read-binary")
def read_file_binary(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    with open(path, "rb") as f:
        return {"content": base64.b64encode(f.read()).decode()}


@app.post("/cleanup")
def cleanup_output():
    output_dir = os.path.join(HOME, "output")
    if os.path.exists(output_dir):
        subprocess.run(["rm", "-rf", f"{output_dir}/*"])
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
