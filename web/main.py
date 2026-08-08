import os
import shutil
from fastapi import FastAPI, UploadFile, File, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from celery import Celery

app = FastAPI(title="aNOTATE Dashboard")

# Celery client configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
celery_app = Celery('anotate_web', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

# Mount media directory for serving generated audio stems and MIDI
MEDIA_DIR = "/app/media"
os.makedirs(MEDIA_DIR, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/upload")
async def upload_audio(file: UploadFile = File(...)):
    file_path = os.path.join(MEDIA_DIR, file.filename)
    base_name = os.path.splitext(file.filename)[0]
    output_midi = os.path.join(MEDIA_DIR, f"{base_name}_output.mid")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Dispatch task to worker
    task = celery_app.send_task(
        "process_audio_to_midi",
        args=[file_path, output_midi]
    )
    
    return {"task_id": task.id, "filename": file.filename}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    res = celery_app.AsyncResult(task_id)
    if res.ready():
        return {"status": res.status, "result": res.result}
    return {"status": res.status}