from typing import Any, Dict, List, Optional
import os
from datetime import datetime
from pymongo import MongoClient

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "educhain")

_client: Optional[MongoClient] = None
_db = None

try:
    _client = MongoClient(DATABASE_URL)
    _db = _client[DATABASE_NAME]
except Exception as e:
    _client = None
    _db = None


def db():
    return _db


def create_document(collection_name: str, data: Dict[str, Any]) -> str:
    if _db is None:
        raise RuntimeError("Database not initialized")
    data = {**data, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
    res = _db[collection_name].insert_one(data)
    return str(res.inserted_id)


def get_documents(collection_name: str, filter_dict: Dict[str, Any] | None = None, limit: int = 100) -> List[Dict[str, Any]]:
    if _db is None:
        raise RuntimeError("Database not initialized")
    filter_dict = filter_dict or {}
    cursor = _db[collection_name].find(filter_dict).limit(limit)
    out: List[Dict[str, Any]] = []
    for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        out.append(doc)
    return out
