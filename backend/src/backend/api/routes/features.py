"""Runtime feature availability for the web client."""

from fastapi import APIRouter, Depends

from backend.api.schemas import FeatureFlags
from backend.api.security import get_current_user
from backend.config import settings

router = APIRouter()


@router.get("/features", response_model=FeatureFlags)
def get_features(_user: dict = Depends(get_current_user)) -> FeatureFlags:
    return FeatureFlags(agent_enabled=settings.agent_enabled)
