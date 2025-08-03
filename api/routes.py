from fastapi import APIRouter

router = APIRouter()

@router.get("/items/")
async def read_items():
    return [{"item_id": 1, "name": "Item One"}, {"item_id": 2, "name": "Item Two"}]

@router.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id, "name": f"Item {item_id}"}