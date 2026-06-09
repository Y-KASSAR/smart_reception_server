import uvicorn
from config.settings import settings
from config.logging_config import setup_logging

if __name__ == "__main__":
    setup_logging()
    uvicorn.run(
        "api.app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.debug,
    )