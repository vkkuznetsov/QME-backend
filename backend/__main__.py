import uvicorn

from backend.project.config import get_config
from backend.setup import get_app

config = get_config()
app = get_app()


if __name__ == "__main__":
    host = config.app_settings.HOST
    port = config.app_settings.PORT
    reload = config.app_settings.RELOAD
    uvicorn.run('backend.setup:get_app', host=host, port=port, reload=reload)