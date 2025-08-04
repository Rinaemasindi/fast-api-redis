import redis.asyncio as redis
import asyncio
import logging
from typing import Optional, Union
import json
import time
import os

def setup_redis_logging():
    """Setup Redis-specific logging that doesn't interfere with other modules"""
    redis_logger = logging.getLogger('redis_api')
    if redis_logger.handlers:
        return redis_logger
    formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s:%(message)s")
    if os.name != "posix":
        log_file = "/laragon/www/logs/redis_api/redis.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    else:
        log_file = "/var/log/api/redis.log"
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
        except PermissionError:
            log_file = "./logs/redis.log"
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
    # Create handlers for Redis logger only
    file_handler = logging.FileHandler(log_file, encoding="utf8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    if os.name != "posix":
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        redis_logger.addHandler(console_handler)
    
    redis_logger.addHandler(file_handler)
    redis_logger.setLevel(logging.INFO)
    redis_logger.propagate = False
    return redis_logger

redis_logger = setup_redis_logging()
def get_log_file_path():
    if os.name != "posix":
        return "/laragon/www/logs/redis_api/redis.log"
    else:
        return "/var/log/api/redis.log"
log_file_path = get_log_file_path()

class RedisConnectionError(Exception):
    """Custom exception for Redis connection errors"""
    pass

class RedisManager:
    def __init__(self, 
                 host: str = 'localhost',
                 port: int = 6379,
                 db: int = 0,
                 max_connections: int = 20,
                 retry_attempts: int = 3,
                 retry_delay: float = 1.0,
                 health_check_interval: int = 30):
        self.host = host
        self.port = port
        self.db = db
        self.max_connections = max_connections
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.health_check_interval = health_check_interval
        self.redis: Optional[redis.Redis] = None
        self._is_connected = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._connection_lock = asyncio.Lock()
        self.logger = redis_logger
    
    async def connect(self, startup_required: bool = False) -> bool:
        """Connect to Redis with retry logic"""
        async with self._connection_lock:
            if self._is_connected and self.redis:
                return True
            
            for attempt in range(self.retry_attempts):
                try:
                    self.redis = redis.Redis(
                        host=self.host,
                        port=self.port,
                        db=self.db,
                        max_connections=self.max_connections,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True,
                        health_check_interval=self.health_check_interval
                    )
                    
                    await asyncio.wait_for(self.redis.ping(), timeout=5.0)
                    self._is_connected = True
                    
                    if not self._health_check_task or self._health_check_task.done():
                        self._health_check_task = asyncio.create_task(self._health_check_loop())
                    
                    self.logger.info(f"Connected to Redis at {self.host}:{self.port}")
                    return True
                    
                except (redis.ConnectionError, redis.TimeoutError, asyncio.TimeoutError) as e:
                    self.logger.warning(f"Redis connection attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
                    if attempt < self.retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    
                except Exception as e:
                    self.logger.error(f"Unexpected error connecting to Redis: {e}")
                    break
            
            self._is_connected = False
            error_msg = f"Failed to connect to Redis after {self.retry_attempts} attempts"
            
            if startup_required:
                raise RedisConnectionError(error_msg)
            else:
                self.logger.warning(f"{error_msg}. Application will continue without Redis.")
                return False
    
    async def disconnect(self):
        """Gracefully disconnect from Redis"""
        async with self._connection_lock:
            self._is_connected = False
            
            if self._health_check_task and not self._health_check_task.done():
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass

            if self.redis:
                try:
                    await self.redis.close()
                    self.logger.info("Disconnected from Redis")
                except Exception as e:
                    self.logger.error(f"Error disconnecting from Redis: {e}")
                finally:
                    self.redis = None
    
    async def _health_check_loop(self):
        """Background task to monitor Redis health"""
        while self._is_connected:
            try:
                await asyncio.sleep(self.health_check_interval)
                if self.redis:
                    await asyncio.wait_for(self.redis.ping(), timeout=3.0)
                    self.logger.debug("Redis health check passed")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning(f"Redis health check failed: {e}")
                self._is_connected = False
                try:
                    await self.connect(startup_required=False)
                except Exception as reconnect_error:
                    self.logger.error(f"Auto-reconnect failed: {reconnect_error}")
    
    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute Redis operation with retry logic and error handling"""
        if not self._is_connected or not self.redis:
            if not await self.connect(startup_required=False):
                raise RedisConnectionError("Redis is not available")
        
        last_exception = None
        for attempt in range(self.retry_attempts):
            try:
                return await operation(*args, **kwargs)
            except (redis.ConnectionError, redis.TimeoutError) as e:
                last_exception = e
                self.logger.warning(f"Redis operation failed (attempt {attempt + 1}/{self.retry_attempts}): {e}")
                
                self._is_connected = False
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
                    await self.connect(startup_required=False)
            except redis.ResponseError as e:
                self.logger.error(f"Redis response error: {e}")
                raise
            except Exception as e:
                self.logger.error(f"Unexpected Redis error: {e}")
                raise
        
        raise RedisConnectionError(f"Redis operation failed after {self.retry_attempts} attempts: {last_exception}")
    
    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        return self._is_connected and self.redis is not None
    
    async def health_check(self) -> dict:
        """Get Redis health status"""
        try:
            if not self.redis:
                return {"status": "disconnected", "error": "No Redis connection"}
            
            start_time = time.time()
            await asyncio.wait_for(self.redis.ping(), timeout=3.0)
            response_time = (time.time() - start_time) * 1000
            info = await self.redis.info()
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "uptime_in_seconds": info.get("uptime_in_seconds")
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key with error handling"""
        try:
            return await self._execute_with_retry(self.redis.get, key)
        except RedisConnectionError:
            self.logger.error(f"Failed to get key '{key}' - Redis unavailable")
            return None
        except Exception as e:
            self.logger.error(f"Error getting key '{key}': {e}")
            return None
    
    async def set(self, key: str, value: Union[str, dict, list, int, float], expire: Optional[int] = None) -> bool:
        """
        Stores a key-value pair in Redis with optional expiration, automatically serializing
        dictionaries and lists to JSON strings. Handles connection errors gracefully.
        Args:
            key (str): The Redis key to set.
            value (Union[str, dict, list, int, float]): The value to store. If a dict or list,
                it will be serialized to a JSON string. Other types are converted to string.
                # Example values:
                # "username"
                # {"user_id": 123, "name": "Alice"}
                # [1, 2, 3]
                # 42
                # 3.14
            expire (Optional[int], optional): Expiration time in seconds. If None, the key does not expire.
        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif not isinstance(value, str):
                value = str(value)
            
            result = await self._execute_with_retry(self.redis.set, key, value, ex=expire)
            return bool(result)
        except RedisConnectionError:
            self.logger.error(f"Failed to set key '{key}' - Redis unavailable")
            return False
        except Exception as e:
            self.logger.error(f"Error setting key '{key}': {e}")
            return False
    
    async def get_json(self, key: str) -> Optional[Union[dict, list]]:
        """Get and automatically deserialize JSON value"""
        try:
            value = await self.get(key)
            if value is None:
                return None
            return json.loads(value)
        except json.JSONDecodeError:
            self.logger.warning(f"Key '{key}' contains invalid JSON")
            return None
        except Exception as e:
            self.logger.error(f"Error getting JSON key '{key}': {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete key with error handling"""
        try:
            result = await self._execute_with_retry(self.redis.delete, key)
            return bool(result)
        except RedisConnectionError:
            self.logger.error(f"Failed to delete key '{key}' - Redis unavailable")
            return False
        except Exception as e:
            self.logger.error(f"Error deleting key '{key}': {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            result = await self._execute_with_retry(self.redis.exists, key)
            return bool(result)
        except RedisConnectionError:
            self.logger.error(f"Failed to check key '{key}' - Redis unavailable")
            return False
        except Exception as e:
            self.logger.error(f"Error checking key '{key}': {e}")
            return False

# CREATE SINGLE GLOBAL INSTANCE
redis_manager = RedisManager(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 0)),
    max_connections=int(os.getenv('REDIS_MAX_CONNECTIONS', 20)),
    retry_attempts=int(os.getenv('REDIS_RETRY_ATTEMPTS', 3)),
    retry_delay=float(os.getenv('REDIS_RETRY_DELAY', 1.0))
)