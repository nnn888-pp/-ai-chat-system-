from __future__ import annotations

from fastapi import APIRouter, Depends

from ..models import User
from ..schemas import UnifiedResponse
from ..services.model_service import ModelService
from .deps import get_current_user

router = APIRouter(prefix="/models", tags=["models"])


def _ok(data):
    return UnifiedResponse(code=0, message="ok", data=data)


@router.get("", response_model=UnifiedResponse)
def list_models(current: User = Depends(get_current_user)):
    return _ok({"list": ModelService.list_models()})


@router.post("/refresh", response_model=UnifiedResponse)
def refresh(current: User = Depends(get_current_user)):
    return _ok({"list": ModelService.refresh_models()})


@router.post("/{model_key}/load", response_model=UnifiedResponse)
def load(model_key: str, current: User = Depends(get_current_user)):
    return _ok(ModelService.load_model(model_key))
