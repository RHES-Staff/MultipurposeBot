"""/api/staff/* Handlers."""

from fastapi.routing import APIRouter

router = APIRouter()


@router.get("/message")
async def send_message() -> dict[str, str]:
    """Test."""
    return {"status": "sent"}
