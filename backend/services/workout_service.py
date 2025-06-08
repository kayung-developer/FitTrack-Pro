from backend import models, schemas, crud
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional


def generate_ai_workout_recommendations(
        db: Session,
        user: models.User,
        recent_activities: Optional[List[schemas.ActivitySchema]] = None,
        user_preferences: Optional[Dict[str, Any]] = None
        # e.g., {"preferred_duration_min": 60, "available_equipment": ["dumbbells", "bench"]}
) -> List[schemas.WorkoutCreate]:
    """
    CONCEPTUAL: AI-based workout recommendations.
    In a real system, this would use user data, goals, performance history, preferences,
    and possibly a model trained on exercise science principles.
    """
    recommendations = []
    goals = user.fitness_goals.lower() if user.fitness_goals else "general fitness"

    print(f"Conceptual: Generating AI workout for user {user.id}, goals: '{goals}'")

    # Example: Simple recommendation based on goal, fetching real exercises from DB

    # Helper to get some exercises
    def get_exercises_by_target(target_keyword: str, limit: int = 3) -> List[models.Exercise]:
        # This is a very basic way to get exercises. A real system would have better tagging.
        return db.query(models.Exercise).filter(models.Exercise.target_muscles.ilike(f"%{target_keyword}%")).limit(
            limit).all()

    if "strength" in goals:
        push_exercises = get_exercises_by_target("chest", 1) + get_exercises_by_target("shoulders",
                                                                                       1) + get_exercises_by_target(
            "triceps", 1)
        pull_exercises = get_exercises_by_target("back", 2) + get_exercises_by_target("biceps", 1)
        leg_exercises = get_exercises_by_target("quads", 1) + get_exercises_by_target("hamstrings",
                                                                                      1) + get_exercises_by_target(
            "glutes", 1)

        if push_exercises:
            recs_push = [schemas.WorkoutExerciseCreate(exercise_id=ex.id, sets=3, reps="8-12") for ex in push_exercises]
            recommendations.append(schemas.WorkoutCreate(name="AI: Strength - Push Day",
                                                         description="AI Recommended push-focused strength workout.",
                                                         workout_exercises=recs_push))
        if pull_exercises:
            recs_pull = [schemas.WorkoutExerciseCreate(exercise_id=ex.id, sets=3, reps="8-12") for ex in pull_exercises]
            recommendations.append(schemas.WorkoutCreate(name="AI: Strength - Pull Day",
                                                         description="AI Recommended pull-focused strength workout.",
                                                         workout_exercises=recs_pull))
        if leg_exercises:
            recs_legs = [schemas.WorkoutExerciseCreate(exercise_id=ex.id, sets=4, reps="10-15") for ex in leg_exercises]
            recommendations.append(schemas.WorkoutCreate(name="AI: Strength - Leg Day",
                                                         description="AI Recommended leg-focused strength workout.",
                                                         workout_exercises=recs_legs))

    if "cardio" in goals or "endurance" in goals:
        # Cardio workouts might not always have specific "exercises" in the same way.
        # This could be represented as a single "activity" type workout.
        # For this structure, we'll leave workout_exercises empty or create a generic "Cardio Session" exercise.
        recommendations.append(schemas.WorkoutCreate(name="AI: Cardio Focus - 30 Min Run",
                                                     description="AI Recommended: 30 minute steady-state run.",
                                                     workout_exercises=[]))
        recommendations.append(schemas.WorkoutCreate(name="AI: HIIT Cardio",
                                                     description="AI Recommended: 20 minute High-Intensity Interval Training.",
                                                     workout_exercises=[]))

    if not recommendations:  # Default if no specific goal match or no exercises found
        general_exercises = db.query(models.Exercise).limit(3).all()
        if general_exercises:
            recs_general = [schemas.WorkoutExerciseCreate(exercise_id=ex.id, sets=3, reps="10-15") for ex in
                            general_exercises]
            recommendations.append(schemas.WorkoutCreate(name="AI: General Fitness Routine",
                                                         description="AI Recommended general fitness workout.",
                                                         workout_exercises=recs_general))
        else:
            recommendations.append(schemas.WorkoutCreate(name="AI: Bodyweight Circuit (Default)",
                                                         description="Perform a 20-min bodyweight circuit (e.g., squats, push-ups, planks).",
                                                         workout_exercises=[]))

    # This is highly simplified. A real system would be much more sophisticated, considering:
    # - Progressive overload
    # - User's current fitness level (from metrics and past workouts)
    # - Exercise variety and muscle group splits
    # - Rest and recovery
    # - Available equipment from user_preferences
    # - Feedback from previous AI-recommended workouts

    return recommendations[:3]  # Return up to 3 suggestions