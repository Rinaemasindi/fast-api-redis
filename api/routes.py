from fastapi import APIRouter
from lib.redis_client import redis_manager
router = APIRouter()

@router.get("/key/")
async def read_items(item_key: str):
    return {"value": await redis_manager.get(item_key   )}

@router.post("/key/")
async def create_item(item_key: str, item_value: str, expire: int = None):
    return {"success": await redis_manager.set(item_key, item_value, expire)}

@router.delete("/key/")
async def delete_item(item_key: str):
    return {"success": await redis_manager.delete(item_key)}