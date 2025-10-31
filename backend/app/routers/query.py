from fastapi import APIRouter


router = APIRouter()


@router.get("/hello")
async def hello_query():
    return {"query": "ok"}


