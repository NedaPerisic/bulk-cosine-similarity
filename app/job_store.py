from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
import threading


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStore:
    """
    In-memory job storage.
    For production with multiple workers, use Redis instead.
    """
    
    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def create_job(self, job_id: str, metadata: dict) -> dict:
        with self._lock:
            now = datetime.utcnow().isoformat()
            self._jobs[job_id] = {
                "status": JobStatus.QUEUED,
                "metadata": metadata,
                "progress": None,
                "result": None,
                "error": None,
                "created_at": now,
                "updated_at": now
            }
            return self._jobs[job_id]
    
    def get_job(self, job_id: str) -> Optional[dict]:
        return self._jobs.get(job_id)
    
    def update_status(
        self, 
        job_id: str, 
        status: JobStatus, 
        progress: dict = None,
        result: dict = None,
        error: str = None
    ):
        with self._lock:
            if job_id not in self._jobs:
                return
            
            self._jobs[job_id]["status"] = status
            self._jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
            
            if progress is not None:
                self._jobs[job_id]["progress"] = progress
            if result is not None:
                self._jobs[job_id]["result"] = result
            if error is not None:
                self._jobs[job_id]["error"] = error
    
    def list_jobs(self, limit: int = 20) -> list:
        """List recent jobs"""
        jobs = list(self._jobs.items())
        jobs.sort(key=lambda x: x[1]["created_at"], reverse=True)
        return [
            {"job_id": jid, **data} 
            for jid, data in jobs[:limit]
        ]
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than max_age_hours"""
        with self._lock:
            now = datetime.utcnow()
            to_delete = []
            for job_id, job in self._jobs.items():
                created = datetime.fromisoformat(job["created_at"])
                age = (now - created).total_seconds() / 3600
                if age > max_age_hours:
                    to_delete.append(job_id)
            
            for job_id in to_delete:
                del self._jobs[job_id]


# Singleton instance
job_store = JobStore()
