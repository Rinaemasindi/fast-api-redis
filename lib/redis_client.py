import redis.asyncio as redis
from typing import Optional

class RedisManager:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        # self.redis = redis.Redis(
        #     host='localhost',
        #     port=6379,
        #     db=0,
        #     decode_responses=True
        # )
        # # Test connection
        # await self.redis.ping()
        print("Connected to Redis")
    
    async def disconnect(self):
        if self.redis:
            await self.redis.close()
            print("Disconnected from Redis")
    
    async def get(self, key: str):
        return await self.redis.get(key)
    
    async def set(self, key: str, value: str, expire: int = None):
        return await self.redis.set(key, value, ex=expire)
    
    async def delete(self, key: str):
        return await self.redis.delete(key)

# Create global instance
redis_manager = RedisManager()