from fastapi import FastAPI
from api.routes import router as api_router
from lib.redis_client import redis_manager
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await redis_manager.connect()
    yield
    # Shutdown
    await redis_manager.disconnect()

app = FastAPI(lifespan=lifespan)
app.include_router(api_router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI project!"}