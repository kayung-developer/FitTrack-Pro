from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend import crud, models, schemas as pydantic_schemas
from backend.core import security
from backend.database import get_db
from backend.core.security import get_current_active_user
from backend.services import user_service

router = APIRouter()


@router.get("/me/full-profile",
            response_model=pydantic_schemas.UserSchema)  # Example of getting user with health metrics
async def read_user_me_with_health_metrics(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_active_user)
):
    # Ensure health_metrics are loaded or calculated
    if not current_user.health_metrics:
        user_service.update_or_create_user_derived_health_metrics(db, current_user)
        db.refresh(current_user)  # Refresh to load the relationship if created
    return current_user


@router.put("/me", response_model=pydantic_schemas.UserSchema)
def update_user_me(
        user_in: pydantic_schemas.UserUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_active_user)
):
    updated_user = crud.user.update(db, db_obj=current_user, obj_in=user_in)

    # Recalculate BMI, BMR, TDEE if relevant fields changed
    # UserUpdate schema allows these fields to be None if not provided,
    # so check if they were part of the update payload.
    # The user_in.dict(exclude_unset=True) would be more precise here.
    if user_in.weight_kg is not None or user_in.height_cm is not None or user_in.age is not None:
        user_service.update_or_create_user_derived_health_metrics(db, updated_user)
        db.refresh(updated_user)  # Refresh to get potentially updated health_metrics relationship
    return updated_user


@router.get("/me/health-metrics", response_model=Optional[pydantic_schemas.HealthMetricSchema])
def read_user_health_metrics(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_active_user)
):
    # Try to get existing metrics
    metrics = crud.health_metric.get_by_user_id(db, user_id=current_user.id)
    if not metrics:
        # If no metrics record, try to calculate and create one if profile data exists
        metrics = user_service.update_or_create_user_derived_health_metrics(db, current_user)
        if not metrics:  # Still no metrics (e.g., profile incomplete for calculation)
            # Return 204 No Content or a specific message, instead of 404, if it's expected
            # For this example, let's keep 404 if truly nothing to show.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Health metrics not found. Ensure profile (age, weight, height) is complete, or log metrics manually.")
    return metrics


@router.post("/me/health-metrics", response_model=pydantic_schemas.HealthMetricSchema,
             status_code=status.HTTP_201_CREATED)
def create_or_update_manual_health_metrics(
        # For metrics like body_fat_percentage, hrv that are not auto-calculated from profile
        metric_in: pydantic_schemas.HealthMetricUpdate,  # Use Update schema for partial inputs
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_active_user)
):
    existing_metric = crud.health_metric.get_by_user_id(db, user_id=current_user.id)

    # Always attempt to update profile-derived metrics first
    user_service.update_or_create_user_derived_health_metrics(db, current_user)
    db.refresh(current_user)  # Get the latest state of user and potentially their health_metrics

    # Re-fetch existing_metric as it might have been created/updated by the call above
    existing_metric = crud.health_metric.get_by_user_id(db, user_id=current_user.id)

    if existing_metric:
        # Merge manually provided data (metric_in) with existing data
        updated_metric = crud.health_metric.update(db, db_obj=existing_metric,
                                                   obj_in=metric_in.dict(exclude_unset=True))
        return updated_metric
    else:
        # If no metric record exists even after trying to derive, create one with manual input
        # This path might be less common if update_or_create_user_derived_health_metrics is robust
        create_payload = pydantic_schemas.HealthMetricCreate(**metric_in.dict(exclude_unset=True),
                                                             user_id=current_user.id)
        # Ensure that if only manual fields are provided, calculated fields aren't wrongly set to None
        # The update_or_create_user_derived_health_metrics should ideally handle creating a base record if profile is complete.
        # This branch assumes we are creating a new record primarily with the manual data.

        # We need to fill in BMI/BMR/TDEE if possible from profile, even if creating with manual data.
        calculated_metrics = {}
        if current_user.weight_kg and current_user.height_cm and current_user.age:
            calculated_metrics['bmi'] = user_service.calculate_bmi(current_user.weight_kg, current_user.height_cm)
            user_gender_for_bmr = "male"  # Placeholder
            bmr_val = user_service.calculate_bmr(current_user.weight_kg, current_user.height_cm, current_user.age,
                                                 gender=user_gender_for_bmr)
            if bmr_val:
                calculated_metrics['bmr'] = bmr_val
                calculated_metrics['tdee'] = user_service.calculate_tdee(bmr_val)

        # Merge calculated with provided manual data for creation
        final_create_data = {**calculated_metrics, **metric_in.dict(exclude_unset=True)}
        # Filter out None values to avoid issues with model constraints if any
        final_create_data_filtered = {k: v for k, v in final_create_data.items() if v is not None}

        if not final_create_data_filtered:  # If nothing to create (e.g. empty input and no profile data)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="No data provided to create health metrics and profile is incomplete.")

        create_schema_final = pydantic_schemas.HealthMetricCreate(user_id=current_user.id, **final_create_data_filtered)
        return crud.health_metric.create_with_user(db, obj_in=create_schema_final, user_id=current_user.id)

# Admin routes (conceptual)
# @router.get("/", response_model=List[pydantic_schemas.UserSchema], dependencies=[Depends(security.require_role("admin"))])
# def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
#     users = crud.user.get_multi(db, skip=skip, limit=limit)
#     return users