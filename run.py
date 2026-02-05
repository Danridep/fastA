import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.126.126.0",
        port=8000,
        reload=False,  # Отключите reloader
        log_level="info"
    )