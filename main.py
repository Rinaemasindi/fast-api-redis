from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.routes import router as api_router
import logging
from lib.redis_client import redis_manager, redis_logger
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await redis_manager.connect(startup_required=False)
        redis_logger.info("FastAPI startup completed")
    except Exception as e:
        redis_logger.error(f"Error during startup: {e}")
    
    yield
    try:
        await redis_manager.disconnect()
        redis_logger.info("FastAPI shutdown completed")
    except Exception as e:
        redis_logger.error(f"Error during shutdown: {e}")

app = FastAPI(
    title="Enhanced FastAPI with Redis",
    description="FastAPI application with robust Redis integration",
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    redis_logger.info("Root endpoint accessed")
    return {
        "message": "Welcome to the FastAPI project!",
        "redis_connected": redis_manager.is_connected,
    }

redis_logger.info(f"Redis configuration - Host: {os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}")