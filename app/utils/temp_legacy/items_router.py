from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.item_service import ItemService, get_item_service
from app.models.item import ItemCreate, ItemUpdate, ItemResponse
from app.utils.response_handler import success_response

router = APIRouter(prefix="/items", tags=["Items"])


@router.get("/", summary="List all items")
def list_items(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
    service: ItemService = Depends(get_item_service),
):
    items = service.get_all(skip=skip, limit=limit)
    total = service.count()
    return success_response(
        data={"items": [i.model_dump() for i in items], "total": total, "skip": skip, "limit": limit}
    )


@router.get("/{item_id}", summary="Get item by ID")
def get_item(item_id: str, service: ItemService = Depends(get_item_service)):
    item = service.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found.")
    return success_response(data=item.model_dump())


@router.post("/", status_code=201, summary="Create a new item")
def create_item(payload: ItemCreate, service: ItemService = Depends(get_item_service)):
    item = service.create(payload)
    return success_response(data=item.model_dump(), message="Item created successfully.")


@router.patch("/{item_id}", summary="Update an item")
def update_item(item_id: str, payload: ItemUpdate, service: ItemService = Depends(get_item_service)):
    item = service.update(item_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found.")
    return success_response(data=item.model_dump(), message="Item updated successfully.")


@router.delete("/{item_id}", summary="Delete an item")
def delete_item(item_id: str, service: ItemService = Depends(get_item_service)):
    deleted = service.delete(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found.")
    return success_response(data=None, message="Item deleted successfully.")
