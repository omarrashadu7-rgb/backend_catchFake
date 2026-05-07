
from pymongo import DESCENDING
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timezone
from typing import Optional

from app.models.item import ItemCreate, ItemUpdate, ItemResponse
from app.database.mongodb import get_db


def _serialize(doc: dict) -> dict:
    """Convert MongoDB document to serializable dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


class ItemService:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db["items"]

    def get_all(self, skip: int = 0, limit: int = 20) -> list[ItemResponse]:
        cursor = self.collection.find().sort("created_at", DESCENDING).skip(skip).limit(limit)
        return [ItemResponse(**_serialize(doc)) for doc in cursor]

    def get_by_id(self, item_id: str) -> Optional[ItemResponse]:
        try:
            oid = ObjectId(item_id)
        except InvalidId:
            return None
        doc = self.collection.find_one({"_id": oid})
        if not doc:
            return None
        return ItemResponse(**_serialize(doc))

    def create(self, payload: ItemCreate) -> ItemResponse:
        now = datetime.now(timezone.utc)
        doc = {
            **payload.model_dump(),
            "created_at": now,
            "updated_at": now,
        }
        result = self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return ItemResponse(**_serialize(doc))

    def update(self, item_id: str, payload: ItemUpdate) -> Optional[ItemResponse]:
        try:
            oid = ObjectId(item_id)
        except InvalidId:
            return None
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            return self.get_by_id(item_id)
        updates["updated_at"] = datetime.now(timezone.utc)
        result = self.collection.find_one_and_update(
            {"_id": oid},
            {"$set": updates},
            return_document=True,
        )
        if not result:
            return None
        return ItemResponse(**_serialize(result))

    def delete(self, item_id: str) -> bool:
        try:
            oid = ObjectId(item_id)
        except InvalidId:
            return False
        result = self.collection.delete_one({"_id": oid})
        return result.deleted_count == 1

    def count(self) -> int:
        return self.collection.count_documents({})


def get_item_service() -> ItemService:
    db = get_database()
    return ItemService(db)
