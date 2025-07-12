from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from job_runner import run_downloader, stop_downloader, is_running
import os

app = FastAPI()

# Static and HTML serving
app.mount("/static", StaticFiles(directory="static"), name="static")

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["buzzheavier"]
logs_col = db["logs"]


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    with open("templates/index.html") as f:
        return f.read()


@app.get("/start")
async def start_download(background_tasks: BackgroundTasks):
    if is_running():
        return JSONResponse({"status": "already_running"})
    background_tasks.add_task(run_downloader, logs_col)
    return {"status": "started"}


@app.get("/stop")
async def stop_download():
    stop_downloader()
    return {"status": "stopped"}


@app.get("/status")
async def get_status():
    return {"running": is_running()}


@app.get("/logs")
async def get_logs():
    logs = list(logs_col.find({}, {"_id": 0}))
    return {"logs": logs}
