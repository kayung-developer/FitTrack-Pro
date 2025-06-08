from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime as dt_datetime  # Alias

from backend import crud, models, schemas as pydantic_schemas
from backend.database import get_db
from backend.core.security import get_current_active_user

router = APIRouter()


def _calculate_total_duration(start_time: dt_datetime, end_time: dt_datetime) -> Optional[float]:
    if start_time and end_time and end_time > start_time:
        duration_delta = end_time - start_time
        return round(duration_delta.total_seconds() / 60, 2)
    return None


@router.post("/", response_model=pydantic_schemas.SleepRecordSchema, status_code=status.HTTP_201_CREATED)
def create_sleep_record_for_current_user(
        sleep_in: pydantic_schemas.SleepRecordCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    # Calculate total duration if not provided but start/end times are
    if sleep_in.total_duration_minutes is None and sleep_in.start_time and sleep_in.end_time:
        sleep_in.total_duration_minutes = _calculate_total_duration(sleep_in.start_time, sleep_in.end_time)

    # Placeholder for smart rest/recovery suggestions based on this sleep record
    # e.g., if sleep_score is low, suggest lighter activity next day via a notification system (not implemented here)
    # This would likely involve a call to an AI/rules-based service.
    # if sleep_in.sleep_score and sleep_in.sleep_score < 60:
    #     print(f"User {current_user.id} had low sleep score ({sleep_in.sleep_score}). Suggest recovery.")

    return crud.sleep_record.create_with_user(db=db, obj_in=sleep_in, user_id=current_user.id)


@router.get("/", response_model=List[pydantic_schemas.SleepRecordSchema])
def read_sleep_records_for_current_user(
        skip: int = 0,
        limit: int = Query(default=10, ge=1, le=30),  # Typically users view sleep over a month
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    sleep_records = crud.sleep_record.get_multi_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return sleep_records


@router.get("/{record_id}", response_model=pydantic_schemas.SleepRecordSchema)
def read_single_sleep_record(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_record = crud.sleep_record.get(db, id=record_id)
    if not db_record or db_record.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sleep record not found or not authorized")
    return db_record


@router.put("/{record_id}", response_model=pydantic_schemas.SleepRecordSchema)
def update_user_sleep_record(
        record_id: int,
        sleep_in: pydantic_schemas.SleepRecordUpdate,  # Use Update schema
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_record = crud.sleep_record.get(db, id=record_id)
    if not db_record or db_record.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sleep record not found or not authorized")

    update_data = sleep_in.dict(exclude_unset=True)

    # Recalculate duration if start_time or end_time is being updated
    # Need original values if only one is changing.
    current_start = db_record.start_time
    current_end = db_record.end_time

    if "start_time" in update_data: current_start = update_data["start_time"]
    if "end_time" in update_data: current_end = update_data["end_time"]

    if "start_time" in update_data or "end_time" in update_data or "total_duration_minutes" not in update_data:
        # If total_duration_minutes is not explicitly provided in the update, recalculate it
        # based on potentially new start/end times.
        # If it IS provided, we trust the user's input for it.
        if "total_duration_minutes" not in update_data or update_data.get("total_duration_minutes") is None:
            update_data["total_duration_minutes"] = _calculate_total_duration(current_start, current_end)

    return crud.sleep_record.update(db, db_obj=db_record, obj_in=update_data)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_sleep_record(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_record = crud.sleep_record.get(db, id=record_id)
    if not db_record or db_record.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sleep record not found or not authorized")
    crud.sleep_record.remove(db, id=record_id)
    return