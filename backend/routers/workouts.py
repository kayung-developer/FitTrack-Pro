from fastapi import APIRouter, Depends, HTTPException, Query, status, Body, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel  # For simple request bodies not in main schemas

from backend import crud, models, schemas as pydantic_schemas
from backend.database import get_db
from backend.core.security import get_current_active_user
from backend.services import workout_service, cv_service

router = APIRouter()


# --- Exercises (Admin/Shared resource, or could be user-specific) ---
@router.post("/exercises", response_model=pydantic_schemas.ExerciseSchema, status_code=status.HTTP_201_CREATED)
def create_new_exercise_definition(  # Renamed for clarity
        exercise_in: pydantic_schemas.ExerciseCreate,
        db: Session = Depends(get_db)
        # Add admin protection if this is a global resource:
        # current_user: models.User = Depends(security.require_role("admin"))
):
    db_exercise = crud.exercise.get_by_name(db, name=exercise_in.name)
    if db_exercise:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise with this name already exists")
    return crud.exercise.create(db=db, obj_in=exercise_in)


@router.get("/exercises", response_model=List[pydantic_schemas.ExerciseSchema])
def list_all_exercise_definitions(
        skip: int = 0,
        limit: int = Query(default=100, ge=1, le=500),
        db: Session = Depends(get_db)
):
    exercises = crud.exercise.get_multi(db, skip=skip, limit=limit)
    return exercises


@router.get("/exercises/{exercise_id}", response_model=pydantic_schemas.ExerciseSchema)
def get_exercise_definition(exercise_id: int, db: Session = Depends(get_db)):
    db_exercise = crud.exercise.get(db, id=exercise_id)
    if not db_exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise definition not found")
    return db_exercise


# --- Workouts for current user ---
@router.post("/", response_model=pydantic_schemas.WorkoutSchema, status_code=status.HTTP_201_CREATED)
def create_workout_plan_for_current_user(
        workout_in: pydantic_schemas.WorkoutCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    return crud.workout.create_with_user(db=db, obj_in=workout_in, user_id=current_user.id)


@router.get("/", response_model=List[pydantic_schemas.WorkoutSchema])
def read_workout_plans_for_current_user(
        skip: int = 0,
        limit: int = Query(default=10, ge=1, le=50),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    workouts = crud.workout.get_multi_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return workouts


@router.get("/{workout_id}", response_model=pydantic_schemas.WorkoutSchema)
def read_single_workout_plan(
        workout_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_workout = crud.workout.get(db, id=workout_id)
    if db_workout is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout plan not found")
    if db_workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this workout plan")
    return db_workout


@router.put("/{workout_id}", response_model=pydantic_schemas.WorkoutSchema)
def update_user_workout_plan(
        workout_id: int,
        workout_in: pydantic_schemas.WorkoutUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_workout = crud.workout.get(db, id=workout_id)
    if db_workout is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout plan not found")
    if db_workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this workout plan")

    # Handle completion date logic if `is_completed` is being changed
    if workout_in.is_completed is not None:
        if workout_in.is_completed and not db_workout.is_completed:  # Marking as complete
            workout_in.completion_date = datetime.utcnow()  # Set completion_date from schema if provided, else now
            if not hasattr(workout_in,
                           'completion_date') or workout_in.completion_date is None:  # Explicitly set if not in payload
                update_data_dict = workout_in.dict(exclude_unset=True)
                update_data_dict['completion_date'] = datetime.utcnow()
                workout_in = pydantic_schemas.WorkoutUpdate(**update_data_dict)  # Recreate schema with date

        elif not workout_in.is_completed and db_workout.is_completed:  # Un-completing
            # Set completion_date to None. Ensure schema allows this or handle dict update.
            update_data_dict = workout_in.dict(exclude_unset=True)
            update_data_dict['completion_date'] = None
            workout_in = pydantic_schemas.WorkoutUpdate(**update_data_dict)

    return crud.workout.update(db=db, db_obj=db_workout, obj_in=workout_in)


@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_workout_plan(
        workout_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_workout = crud.workout.get(db, id=workout_id)
    if db_workout is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout plan not found")
    if db_workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this workout plan")
    crud.workout.remove(db, id=workout_id)
    return


# --- AI Workout Recommendations ---
class AIRecommendationPrefs(BaseModel):  # Example schema for preferences
    preferred_duration_min: Optional[int] = Query(None, ge=10, le=180)
    available_equipment: Optional[List[str]] = None
    focus_areas: Optional[List[str]] = None  # e.g., "upper_body", "core", "flexibility"


@router.post("/ai-recommendations", response_model=List[pydantic_schemas.WorkoutCreate])
def get_ai_workout_recommendations(
        preferences: Optional[AIRecommendationPrefs] = Body(None),  # User can optionally send preferences
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    recent_activities_db = crud.activity.get_multi_by_user(db, user_id=current_user.id,
                                                           limit=10)  # Get recent activities for context
    recent_activities_schemas = [pydantic_schemas.ActivitySchema.from_orm(act) for act in recent_activities_db]

    recommendations = workout_service.generate_ai_workout_recommendations(
        db=db,  # Pass db session to service if it needs to query exercises
        user=current_user,
        recent_activities=recent_activities_schemas,
        user_preferences=preferences.dict() if preferences else None
    )
    if not recommendations:
        return []
    return recommendations


# --- CV Pose Estimation Feedback ---
@router.post(
    "/{workout_id}/workout-exercise/{workout_exercise_id}/analyze-form",
    response_model=pydantic_schemas.PoseEstimationFeedback
)
async def analyze_exercise_form_with_cv(
        workout_id: int,
        workout_exercise_id: int,  # This is the ID of the models.WorkoutExercise instance
        request_data: pydantic_schemas.PoseEstimationRequest,  # Contains exercise_type and base64 frames
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_workout = crud.workout.get(db, id=workout_id)
    if not db_workout or db_workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found or not authorized")

    target_wo_exercise_assoc: Optional[models.WorkoutExercise] = None
    for wea in db_workout.workout_exercises_association:
        if wea.id == workout_exercise_id:
            target_wo_exercise_assoc = wea
            break

    if not target_wo_exercise_assoc or not target_wo_exercise_assoc.exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Workout Exercise with ID {workout_exercise_id} not found in this workout, or exercise definition missing.")

    # Use exercise name from DB if exercise_type in request_data is just a fallback
    exercise_name_for_cv = target_wo_exercise_assoc.exercise.name

    analysis_result_dict = cv_service.analyze_exercise_form_from_frames(
        video_frames_base64=request_data.video_frames_base64,
        exercise_type=exercise_name_for_cv  # Use name from DB for consistency
    )

    if "error" in analysis_result_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=analysis_result_dict["error"])

    # Store feedback in the workout's JSON field, keyed by workout_exercise_id
    if db_workout.pose_estimation_feedback is None:
        db_workout.pose_estimation_feedback = {}

    # Store history of analyses for this exercise in this workout, or just latest
    # For simplicity, storing latest or appending to a list
    feedback_list_for_exercise = db_workout.pose_estimation_feedback.get(str(workout_exercise_id), [])
    feedback_list_for_exercise.append(analysis_result_dict)  # Append new analysis
    db_workout.pose_estimation_feedback[str(workout_exercise_id)] = feedback_list_for_exercise[
                                                                    -3:]  # Keep last 3 analyses

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(db_workout, "pose_estimation_feedback")  # Important for JSON field changes

    try:
        db.commit()
        db.refresh(db_workout)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to save CV feedback: {e}")

    return pydantic_schemas.PoseEstimationFeedback(**analysis_result_dict)