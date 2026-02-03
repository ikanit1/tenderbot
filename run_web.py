# run_web.py — запуск веб-админки (отдельно от бота)
# Использование: python run_web.py  или  uvicorn web.main:app --host 0.0.0.0 --port 8000
import uvicorn
from config import settings

if __name__ == "__main__":
    uvicorn.run(
        "web.main:app",
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        reload=False,
    )
