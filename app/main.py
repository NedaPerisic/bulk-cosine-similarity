import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

from .calculator import CosineCalculatorService
from .job_store import job_store, JobStatus

# ============================================================
# LIFESPAN - Initialize/cleanup resources
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Cosine Similarity API...")
    yield
    # Shutdown
    print("👋 Shutting down...")


# ============================================================
# FASTAPI APP
# ============================================================
app = FastAPI(
    title="Cosine Similarity API",
    description="Calculate semantic similarity between article and target URLs",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================
class WebhookRequest(BaseModel):
    spreadsheet_id: str
    sheet_name: str = "Sheet1"
    article_column: str = "A"
    target_column: str = "B"
    output_column: str = "C"
    threshold_column: Optional[str] = None  # Auto: next to output
    
    class Config:
        json_schema_extra = {
            "example": {
                "spreadsheet_id": "1L7Kbc7Ye_DBOTFaiU3cnY-lVCBRilFxc0bkLKALvsRA",
                "sheet_name": "Sheet1",
                "article_column": "A",
                "target_column": "B",
                "output_column": "C"
            }
        }


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    status: str
    progress: Optional[dict] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


# ============================================================
# BACKGROUND TASK
# ============================================================
async def process_spreadsheet_job(job_id: str, request: WebhookRequest):
    """Background task that processes the spreadsheet"""
    try:
        job_store.update_status(job_id, JobStatus.PROCESSING, progress={"stage": "initializing"})
        
        # Run in thread pool (CPU-bound + blocking I/O)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            CosineCalculatorService.process_spreadsheet,
            request.spreadsheet_id,
            request.sheet_name,
            request.article_column,
            request.target_column,
            request.output_column,
            request.threshold_column,
            lambda prog: job_store.update_status(job_id, JobStatus.PROCESSING, progress=prog)
        )
        
        job_store.update_status(job_id, JobStatus.COMPLETED, result=result)
        
    except Exception as e:
        job_store.update_status(job_id, JobStatus.FAILED, error=str(e))
        print(f"❌ Job {job_id} failed: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# ENDPOINTS
# ============================================================
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Cosine Similarity API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check for Railway"""
    return {"status": "healthy"}


@app.post("/webhook", response_model=JobResponse)
async def create_job(request: WebhookRequest, background_tasks: BackgroundTasks):
    """
    Receive webhook from n8n, start processing job.
    Returns immediately with job_id for status polling.
    """
    job_id = str(uuid.uuid4())[:8]
    
    # Create job entry
    job_store.create_job(job_id, {
        "spreadsheet_id": request.spreadsheet_id,
        "sheet_name": request.sheet_name
    })
    
    # Schedule background processing
    background_tasks.add_task(process_spreadsheet_job, job_id, request)
    
    return JobResponse(
        job_id=job_id,
        status="queued",
        message=f"Job created. Poll /status/{job_id} for progress."
    )


@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """Get job status and progress"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        result=job.get("result"),
        error=job.get("error"),
        created_at=job["created_at"],
        updated_at=job["updated_at"]
    )


@app.get("/jobs")
async def list_jobs():
    """List all jobs (for debugging)"""
    return {"jobs": job_store.list_jobs()}
