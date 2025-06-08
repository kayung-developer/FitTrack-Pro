from backend import models, schemas
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

# --- CONCEPTUAL Sustainability Service ---

# Example emission factors (kg CO2e per unit). These are highly simplified.
# Real factors are complex and vary by region, equipment efficiency, etc.
EMISSION_FACTORS = {
    "transport": {
        "car_gasoline_small_km": 0.15,  # kg CO2e per km
        "car_electric_km": 0.05,  # (depends on electricity grid mix)
        "public_transport_bus_km": 0.1,
        "bicycle_km": 0.0,
        "walk_km": 0.0
    },
    "activity": {  # Emissions from the activity itself (mostly negligible for personal exercise)
        "running_hour": 0.01,  # (e.g., slightly increased respiration, usually ignored)
        "gym_equipment_usage_hour": 0.05  # (e.g., electricity for treadmill, lights - very rough)
    },
    "food_production_impact_per_100kcal": {  # Extremely simplified placeholder
        "red_meat_based": 0.1,  # High impact
        "poultry_based": 0.04,
        "plant_based": 0.01  # Low impact
    }
}


def calculate_activity_carbon_footprint(
        db: Session,
        user: models.User,
        activity: models.Activity,  # The user's logged activity from DB
        request_data: schemas.ActivityCarbonFootprintRequest
) -> schemas.ActivityCarbonFootprintResponse:
    """
    CONCEPTUAL: Calculates the carbon footprint associated with a fitness activity,
    including transport to/from the activity location.
    """
    print(f"Conceptual Sustainability: Calculating C02 footprint for activity {activity.id} of user {user.id}")

    total_footprint_kg_co2e = 0.0
    breakdown: Dict[str, float] = {}

    # 1. Transport Emissions
    if request_data.transport_mode_to_activity_location and request_data.distance_to_location_km:
        mode = request_data.transport_mode_to_activity_location
        distance_one_way = request_data.distance_to_location_km
        if mode in EMISSION_FACTORS["transport"]:
            emission_factor_transport = EMISSION_FACTORS["transport"][mode]
            transport_emissions = emission_factor_transport * distance_one_way * 2  # Assuming round trip
            total_footprint_kg_co2e += transport_emissions
            breakdown["transport_to_activity"] = round(transport_emissions, 3)
        else:
            print(f"Warning: Unknown transport mode '{mode}' for emission calculation.")

    # 2. Activity-Specific Emissions (usually minor for exercise itself, but can include gym equipment)
    activity_duration_hours = (
                activity.duration_minutes / 60) if activity.duration_minutes else 0.5  # Assume 30 mins if no duration

    # This is very rough; depends on activity type
    activity_emission_factor_key = ""
    if activity.activity_type in [models.ActivityTypeDB.RUNNING, models.ActivityTypeDB.CYCLING,
                                  models.ActivityTypeDB.WALKING] and request_data.transport_mode_to_activity_location == "walk_km":  # outdoor
        activity_emission_factor_key = "running_hour"  # Could be more specific
    elif activity.activity_type in [models.ActivityTypeDB.STRENGTH_TRAINING, models.ActivityTypeDB.HIIT]:  # Likely gym
        activity_emission_factor_key = "gym_equipment_usage_hour"

    if activity_emission_factor_key and activity_emission_factor_key in EMISSION_FACTORS["activity"]:
        activity_emissions = EMISSION_FACTORS["activity"][activity_emission_factor_key] * activity_duration_hours
        total_footprint_kg_co2e += activity_emissions
        breakdown["activity_itself"] = round(activity_emissions, 3)

    # 3. (Future/More Complex) Link to nutrition choices related to fitness goals/recovery
    #    e.g., if user logged a high-impact post-workout meal. This is beyond simple activity tracking.

    suggestions = []
    if breakdown.get("transport_to_activity", 0) > 0.1:  # Arbitrary threshold
        suggestions.append("Consider cycling, walking, or public transport for shorter trips to your workout location.")
    if breakdown.get("activity_itself", 0) > 0.03 and "gym" in activity_emission_factor_key:
        suggestions.append(
            "Opt for bodyweight exercises or outdoor activities occasionally to reduce gym equipment energy use.")

    # Store this calculated footprint (e.g., in a new column on Activity model or a separate log)
    # activity.carbon_footprint_kg_co2e = total_footprint_kg_co2e
    # db.commit()

    return schemas.ActivityCarbonFootprintResponse(
        activity_id=activity.id,
        activity_type=schemas.ActivityTypeSchema(activity.activity_type.value),  # Convert DB enum to schema enum
        estimated_carbon_footprint_kg_co2e=round(total_footprint_kg_co2e, 3),
        breakdown=breakdown if breakdown else None,
        suggestions_for_reduction=suggestions if suggestions else None
    )


def get_user_sustainability_summary(db: Session, user: models.User) -> Dict[str, Any]:
    """CONCEPTUAL: Provides an overview of the user's eco-friendly metrics and impact."""
    print(f"Conceptual Sustainability: Fetching summary for user {user.id}")
    # Fetch all activities with calculated footprints, sum them up.
    # Calculate "green miles" (walked/cycled).
    # Track participation in eco-challenges.
    return {
        "total_estimated_carbon_footprint_last_30_days_kg_co2e": 15.75,  # Mocked
        "total_green_kilometers_walked_cycled_last_30_days": 85.2,  # Mocked
        "active_eco_challenges": ["CycleToWorkoutChallenge"],
        "sustainability_score_percent": 78  # Mocked overall score
    }