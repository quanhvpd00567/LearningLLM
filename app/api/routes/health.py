from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    # Liveness của API; không thực hiện inference hoặc kiểm tra model.
    return {"status": "ok"}
