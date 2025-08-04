from fastapi import FastAPI, APIRouter
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from lib.redis_client import RedisManager as redis_manager, setup_logging
import time
from typing import Optional
import os

log_file_path = setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await redis_manager.connect(startup_required=False)
        logger.info("FastAPI startup completed")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
    yield
    try:
        await redis_manager.disconnect()
        logger.info("FastAPI shutdown completed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

app = FastAPI(
    title="Enhanced FastAPI with Redis",
    description="FastAPI application with robust Redis integration",
    lifespan=lifespan
)

logger.info(f"FastAPI application starting up - Log file: {log_file_path}")
logger.info(f"Redis configuration - Host: {os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}")