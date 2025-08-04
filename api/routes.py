from fastapi import APIRouter
from lib.redis_client import RedisManager as redis_manager, setup_logging
from fastapi import HTTPException
import time
from typing import Optional
import logging
router = APIRouter()

log_file_path = setup_logging()

logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    """Application health check"""
    logger.info("Health check endpoint accessed")
    redis_health = await redis_manager.health_check()
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "redis": redis_health,
        "log_file": log_file_path
    }

@router.get("/health/redis")
async def redis_health_check():
    """Detailed Redis health check"""
    logger.debug("Redis health check endpoint accessed")
    return await redis_manager.health_check()

@router.post("/cache/{key}")
async def set_cache(key: str, value: dict, expire: Optional[int] = None):
    """Set cache value with optional expiration"""
    logger.info(f"Setting cache key: {key}, expire: {expire}")
    try:
        success = await redis_manager.set(key, value, expire)
        if success:
            logger.info(f"Successfully set cache key: {key}")
            return {"message": f"Key '{key}' set successfully", "expires_in": expire}
        else:
            logger.warning(f"Failed to set cache key: {key} - Redis unavailable")
            raise HTTPException(status_code=503, detail="Cache service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in set_cache for key '{key}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/cache/{key}")
async def get_cache(key: str):
    """Get cache value"""
    logger.info(f"Getting cache key: {key}")
    try:
        value = await redis_manager.get_json(key)
        if value is None:
            value = await redis_manager.get(key)
        
        if value is None:
            logger.info(f"Cache key not found: {key}")
            raise HTTPException(status_code=404, detail="Key not found")
        
        logger.info(f"Successfully retrieved cache key: {key}")
        return {"key": key, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_cache for key '{key}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/cache/{key}")
async def delete_cache(key: str):
    """Delete cache key"""
    logger.info(f"Deleting cache key: {key}")
    try:
        success = await redis_manager.delete(key)
        if success:
            logger.info(f"Successfully deleted cache key: {key}")
            return {"message": f"Key '{key}' deleted successfully"}
        else:
            logger.info(f"Cache key not found for deletion: {key}")
            raise HTTPException(status_code=404, detail="Key not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_cache for key '{key}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")