from sqlalchemy.orm import Session
from backend import models, schemas, crud
from typing import Optional


def calculate_bmi(weight_kg: float, height_cm: float) -> Optional[float]:
    if not all([weight_kg, height_cm]) or height_cm <= 0 or weight_kg <= 0:
        return None
    return round(weight_kg / ((height_cm / 100) ** 2), 2)


def calculate_bmr(weight_kg: float, height_cm: float, age_years: int, gender: str = "male") -> Optional[float]:
    """Mifflin-St Jeor Equation for BMR. Gender can be 'male' or 'female'."""
    if not all([weight_kg, height_cm, age_years]) or weight_kg <= 0 or height_cm <= 0 or age_years <= 0:
        return None

    # Ensure gender is lowercase for comparison
    gender_lower = gender.lower() if gender else "male"  # Default to male if gender not provided

    if gender_lower == "male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) + 5
    elif gender_lower == "female":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) - 161
    else:  # Fallback for other gender inputs or if gender is not strictly 'male'/'female'
        # Could use an average or a specific formula if defined for non-binary individuals,
        # or stick to one as a default. For this example, defaulting to male formula.
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) + 5
    return round(bmr, 2)


def calculate_tdee(bmr: float, activity_level_multiplier: float = 1.2) -> Optional[float]:
    """TDEE = BMR * Activity Level Multiplier. Default multiplier is for sedentary."""
    if bmr <= 0:
        return None
    return round(bmr * activity_level_multiplier, 2)


def update_or_create_user_derived_health_metrics(db: Session, user: models.User) -> Optional[models.HealthMetric]:
    if not all([user.weight_kg, user.height_cm, user.age]):
        # Not enough data on user profile to calculate all metrics
        # Check if an existing metric record needs only partial update (e.g., from body_fat_percentage direct input)
        existing_metric = crud.health_metric.get_by_user_id(db, user_id=user.id)
        if existing_metric: return existing_metric  # Return existing if no profile data to recalc
        return None

    # Assuming gender is not explicitly stored on User model for BMR calculation.
    # We can pass a default or try to infer. For now, using default "male".
    # This should be enhanced if gender information is available and relevant for the user.
    user_gender_for_bmr = "male"  # Placeholder: enhance User model or pass from profile if available

    bmi = calculate_bmi(user.weight_kg, user.height_cm)
    bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, gender=user_gender_for_bmr)
    # TDEE calculation needs an activity level. This is a simplification.
    # A real app would get activity level from user settings or derive from logged activities.
    tdee = calculate_tdee(bmr) if bmr else None

    metric_data_dict = {"bmi": bmi, "bmr": bmr, "tdee": tdee}
    # Filter out None values to prevent overwriting existing data with None if a calculation failed
    update_payload = {k: v for k, v in metric_data_dict.items() if v is not None}

    existing_metric = crud.health_metric.get_by_user_id(db, user_id=user.id)

    if existing_metric:
        # Update existing metric with newly calculated values
        # Only update if the new value is not None
        updated_metric_obj = crud.health_metric.update(db, db_obj=existing_metric, obj_in=update_payload)
        return updated_metric_obj
    else:
        # Create new metric if some values are calculable
        if any(v is not None for v in update_payload.values()):
            # Include user_id in the create schema
            create_schema = schemas.HealthMetricCreate(**update_payload, user_id=user.id)
            return crud.health_metric.create_with_user(db, obj_in=create_schema, user_id=user.id)
    return None