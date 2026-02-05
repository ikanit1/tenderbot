# web/routes/health.py — health check endpoints
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from web.database import get_db

router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Проверка состояния системы."""
    try:
        # Проверяем подключение к БД
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return JSONResponse({
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "service": "tenderbot",
    })


@router.get("/health/live")
async def liveness_check():
    """Liveness probe для Kubernetes/Docker."""
    return JSONResponse({"status": "alive"})


@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe для Kubernetes/Docker."""
    try:
        db.execute(text("SELECT 1"))
        return JSONResponse({"status": "ready"})
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)
