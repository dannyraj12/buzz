from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from job_runner import run_downloader, stop_downloader, is_running, get_current_stats
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Buzzheavier Auto Downloader", version="1.0.0")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# MongoDB connection with error handling
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # Test connection
    client.admin.command('ping')
    db = client["buzzheavier"]
    logs_col = db["logs"]
    stats_col = db["stats"]
    logger.info("MongoDB connected successfully")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    # Fallback to in-memory storage
    logs_col = None
    stats_col = None


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard"""
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dashboard template not found")


@app.post("/start")
async def start_download(background_tasks: BackgroundTasks):
    """Start the download process"""
    if is_running():
        return JSONResponse({"status": "already_running", "message": "Download process is already running"})
    
    try:
        background_tasks.add_task(run_downloader, logs_col, stats_col)
        logger.info("Download process started")
        return {"status": "started", "message": "Download process initiated successfully"}
    except Exception as e:
        logger.error(f"Failed to start download process: {e}")
        return JSONResponse(
            {"status": "error", "message": f"Failed to start: {str(e)}"}, 
            status_code=500
        )


@app.post("/stop")
async def stop_download():
    """Stop the download process"""
    try:
        stop_downloader()
        logger.info("Download process stopped")
        return {"status": "stopped", "message": "Download process stopped successfully"}
    except Exception as e:
        logger.error(f"Failed to stop download process: {e}")
        return JSONResponse(
            {"status": "error", "message": f"Failed to stop: {str(e)}"}, 
            status_code=500
        )


@app.get("/status")
async def get_status():
    """Get current status and statistics"""
    try:
        stats = get_current_stats()
        return {
            "running": is_running(),
            "stats": stats,
            "timestamp": stats.get("last_updated", "N/A")
        }
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        return {"running": False, "stats": {}, "error": str(e)}


@app.get("/logs")
async def get_logs(limit: int = 50):
    """Get recent logs"""
    try:
        if logs_col is None:
            return {"logs": [], "message": "Database not available"}
        
        logs = list(logs_col.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit))
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        logger.error(f"Failed to fetch logs: {e}")
        return {"logs": [], "error": str(e)}


@app.delete("/logs")
async def clear_logs():
    """Clear all logs"""
    try:
        if logs_col is None:
            return {"message": "Database not available"}
        
        result = logs_col.delete_many({})
        logger.info(f"Cleared {result.deleted_count} log entries")
        return {"message": f"Cleared {result.deleted_count} log entries"}
    except Exception as e:
        logger.error(f"Failed to clear logs: {e}")
        return JSONResponse(
            {"error": f"Failed to clear logs: {str(e)}"}, 
            status_code=500
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected" if logs_col is not None else "disconnected",
        "downloader": "running" if is_running() else "idle"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)