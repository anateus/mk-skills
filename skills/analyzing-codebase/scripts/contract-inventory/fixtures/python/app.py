from fastapi import FastAPI
from routes import router as calls_router
from routes import conditional


def create_app():
    application = FastAPI()
    application.include_router(calls_router, prefix="/v1")
    application.include_router(unresolved_router)
    if feature_enabled:
        application.include_router(conditional)
    return application


app = create_app()
