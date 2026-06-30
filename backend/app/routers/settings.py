from fastapi import APIRouter

from ..models.settings import ModalityRestrictionsPayload
from ..services.settings import get_modality_restrictions_data, set_modality_restrictions_data

router = APIRouter()


@router.get("/settings/modality-restrictions")
def get_modality_restrictions():
    return get_modality_restrictions_data()


@router.put("/settings/modality-restrictions")
def update_modality_restrictions(payload: ModalityRestrictionsPayload):
    return set_modality_restrictions_data(payload.model_dump())
