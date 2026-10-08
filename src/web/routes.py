from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def dashboard():
    return {"status": "ok"}


@router.get("/campaigns")
def campaigns():
    return {"campaigns": []}


@router.get("/search")
def search_form():
    return {"source": "places"}
