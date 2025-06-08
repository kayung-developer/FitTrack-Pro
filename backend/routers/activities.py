from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend import crud, models, schemas as pydantic_schemas, schemas
from backend.database import get_db
from backend.core.security import get_current_active_user
from backend.services import activity_service  # For processing GPS data, etc.

router = APIRouter()


@router.post("/", response_model=pydantic_schemas.ActivitySchema, status_code=status.HTTP_201_CREATED)
def create_activity_for_current_user(
        activity_in: pydantic_schemas.ActivityCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    # Pre-process activity data (e.g., calculate duration from start/end, process GPS)
    processed_activity_in = activity_service.process_activity_data_for_saving(activity_in)

    return crud.activity.create_with_user(db=db, obj_in=processed_activity_in, user_id=current_user.id)


@router.get("/", response_model=List[pydantic_schemas.ActivitySchema])
def read_activities_for_current_user(
        skip: int = 0,
        limit: int = Query(default=20, ge=1, le=100),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    activities = crud.activity.get_multi_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return activities


@router.get("/{activity_id}", response_model=pydantic_schemas.ActivitySchema)
def read_single_activity(
        activity_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_activity = crud.activity.get(db, id=activity_id)
    if db_activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    if db_activity.user_id != current_user.id:
        # Could also return 404 to obscure existence if preferred over 403
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this activity")
    return db_activity


@router.put("/{activity_id}", response_model=pydantic_schemas.ActivitySchema)
def update_user_activity(
        activity_id: int,
        activity_in: pydantic_schemas.ActivityUpdate,  # Use specific Update schema
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_activity = crud.activity.get(db, id=activity_id)
    if db_activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    if db_activity.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this activity")

    # Pre-process update data if necessary (e.g., recalculate duration if start/end times change)
    # This assumes ActivityUpdate can be merged; more complex logic might be needed for partial updates
    # to GPS data or similar complex fields.
    update_data_processed = activity_service.process_activity_data_for_saving(
        schemas.ActivityCreate(**db_activity.__dict__, **activity_in.dict(exclude_unset=True))
    )  # Create a full object then convert to dict for update

    return crud.activity.update(db, db_obj=db_activity, obj_in=update_data_processed.dict(exclude_unset=True))


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_activity(
        activity_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_activity = crud.activity.get(db, id=activity_id)
    if db_activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    if db_activity.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this activity")

    crud.activity.remove(db, id=activity_id)
    return  # No content response