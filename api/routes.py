# api/routes.py - FIXED VERSION with module-specific logging
from fastapi import APIRouter, HTTPException
from lib.redis_client import redis_manager, log_file_path, redis_logger
import time
from typing import Optional

router = APIRouter()

@router.get("/health")
async def health_check():
    """Application health check"""
    redis_logger.info("Health check endpoint accessed")
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
    redis_logger.debug("Redis health check endpoint accessed")
    return await redis_manager.health_check()

@router.post("/cache/{key}")
async def set_cache(key: str, value: dict, expire: Optional[int] = None):
    """Set cache value with optional expiration"""
    redis_logger.info(f"Setting cache key: {key}, expire: {expire}")
    try:
        success = await redis_manager.set(key, value, expire)
        if success:
            redis_logger.info(f"Successfully set cache key: {key}")
            return {"message": f"Key '{key}' set successfully", "expires_in": expire}
        else:
            redis_logger.warning(f"Failed to set cache key: {key} - Redis unavailable")
            raise HTTPException(status_code=503, detail="Cache service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        redis_logger.error(f"Error in set_cache for key '{key}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/cache/{key}")
async def get_cache(key: str):
    """Get cache value"""
    redis_logger.info(f"Getting cache key: {key}")
    try:
        value = await redis_manager.get_json(key)
        if value is None:
            value = await redis_manager.get(key)
        
        if value is None:
            redis_logger.info(f"Cache key not found: {key}")
            raise HTTPException(status_code=404, detail="Key not found")
        
        redis_logger.info(f"Successfully retrieved cache key: {key}")
        return {"key": key, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        redis_logger.error(f"Error in get_cache for key '{key}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/cache/{key}")
async def delete_cache(key: str):
    """Delete cache key"""
    redis_logger.info(f"Deleting cache key: {key}")
    try:
        success = await redis_manager.delete(key)
        if success:
            redis_logger.info(f"Successfully deleted cache key: {key}")
            return {"message": f"Key '{key}' deleted successfully"}
        else:
            redis_logger.info(f"Cache key not found for deletion: {key}")
            raise HTTPException(status_code=404, detail="Key not found")
    except HTTPException:
        raise
    except Exception as e:
        redis_logger.error(f"Error in delete_cache for key '{key}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")