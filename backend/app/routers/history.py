from fastapi import APIRouter
from ..core.database import get_database


router = APIRouter()


@router.get("/hello")
async def hello_history():
    return {"history": "ok"}


@router.get("/db-test")
async def db_test():
    """Simple DB smoke test: insert a sample doc and return counts."""
    db = get_database()
    collection = db["samples"]
    await collection.insert_one({"_seed": "init", "ok": True})
    count = await collection.count_documents({})
    one = await collection.find_one(sort=[("_id", -1)])
    # sanitize ObjectId for JSON response
    if one and "_id" in one:
        one["_id"] = str(one["_id"])
    return {"collection": "samples", "count": count, "last": one}


