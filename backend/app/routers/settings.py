from fastapi import APIRouter

from ..models.settings import AthleteProfilePayload, ModalityRestrictionsPayload, PerformanceSettingsPayload, WorkoutTemplateSettingsPayload
from ..services.settings import (
    get_athlete_profile_data,
    get_modality_restrictions_data,
    get_performance_settings_data,
    get_workout_template_settings_data,
    set_athlete_profile_data,
    set_modality_restrictions_data,
    set_performance_settings_data,
    set_workout_template_settings_data,
)

router = APIRouter()


@router.get("/settings/modality-restrictions")
def get_modality_restrictions():
    return get_modality_restrictions_data()


@router.get("/settings/athlete-profile")
def get_athlete_profile():
    return get_athlete_profile_data()


@router.get("/settings/workout-templates")
def get_workout_templates():
    return get_workout_template_settings_data()


@router.get("/settings/performance")
def get_performance_settings():
    return get_performance_settings_data()


@router.put("/settings/modality-restrictions")
def update_modality_restrictions(payload: ModalityRestrictionsPayload):
    return set_modality_restrictions_data(payload.model_dump())


@router.put("/settings/athlete-profile")
def update_athlete_profile(payload: AthleteProfilePayload):
    return set_athlete_profile_data(payload.model_dump())


@router.put("/settings/workout-templates")
def update_workout_templates(payload: WorkoutTemplateSettingsPayload):
    return set_workout_template_settings_data(payload.model_dump())


@router.put("/settings/performance")
def update_performance_settings(payload: PerformanceSettingsPayload):
    return set_performance_settings_data(payload.model_dump())
