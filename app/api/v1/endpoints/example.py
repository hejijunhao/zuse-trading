from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_examples():
    return {"message": "This is an example endpoint"}


@router.get("/{item_id}")
async def get_example(item_id: int):
    return {"item_id": item_id, "message": "This is an example item"}
