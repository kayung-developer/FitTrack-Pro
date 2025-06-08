from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy import Enum as SAEnum  # To avoid conflict with Python's enum
from sqlalchemy.orm import relationship
from backend.database import Base
from datetime import datetime
import enum  # Python's enum for defining choices


# --- Enums for database choices ---
class ActivityTypeDB(enum.Enum):
    RUNNING = "running"
    CYCLING = "cycling"
    WALKING = "walking"
    SWIMMING = "swimming"
    STRENGTH_TRAINING = "strength_training"
    HIIT = "hiit"
    YOGA = "yoga"
    OTHER = "other"


class PaymentStatusDB(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentGatewayDB(enum.Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    CRYPTO = "crypto"
    MASTERCARD_VISA_VERVE = "card"


# --- SQLAlchemy Models ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Make nullable if Firebase is primary auth
    firebase_uid = Column(String, unique=True, index=True, nullable=True)  # New field

    full_name = Column(String, index=True, nullable=True)
    age = Column(Integer, nullable=True)
    # ... (rest of the User model as before) ...
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    health_metrics = relationship("HealthMetric", back_populates="user", uselist=False, cascade="all, delete-orphan")

    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    workouts = relationship("Workout", back_populates="user", cascade="all, delete-orphan")
    nutrition_logs = relationship("NutritionLog", back_populates="user", cascade="all, delete-orphan")
    sleep_records = relationship("SleepRecord", back_populates="user", cascade="all, delete-orphan")
    payment_records = relationship("PaymentRecord", back_populates="user", cascade="all, delete-orphan")
    # Add relationships for future features here (conceptual models not created for DB brevity)
    # genetic_data_uploads = relationship("GeneticDataUploadRecord", back_populates="user")
    # mental_wellness_logs = relationship("MentalWellnessDBLog", back_populates="user")


class HealthMetric(Base):
    __tablename__ = "health_metrics"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)  # One-to-one with User
    bmi = Column(Float, nullable=True)
    body_fat_percentage = Column(Float, nullable=True)
    bmr = Column(Float, nullable=True)
    tdee = Column(Float, nullable=True)
    hrv = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Last update time

    user = relationship("User", back_populates="health_metrics")


class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activity_type = Column(SAEnum(ActivityTypeDB), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Float, nullable=True)
    distance_km = Column(Float, nullable=True)
    calories_burned = Column(Float, nullable=True)
    avg_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    hr_zones = Column(JSON, nullable=True)
    gps_data = Column(JSON,
                      nullable=True)  # List of {"lat": float, "lon": float, "timestamp": str, "altitude": float, "accuracy": float}
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="activities")


class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    target_muscles = Column(String, nullable=True)  # Could be JSON array string
    equipment_needed = Column(String, nullable=True)
    # video_url = Column(String, nullable=True)

    # Relationship to WorkoutExercise (many-to-many through association)
    # workout_associations = relationship("WorkoutExercise", back_populates="exercise")


class WorkoutExercise(Base):  # Association object for Workout and Exercise
    __tablename__ = "workout_exercises"
    id = Column(Integer, primary_key=True, index=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    sets = Column(Integer, nullable=True)
    reps = Column(String, nullable=True)
    weight_kg = Column(Float, nullable=True)
    rest_seconds = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    # Order within workout can be handled by list order or an explicit order column

    exercise = relationship("Exercise")  # , back_populates="workout_associations")
    workout = relationship("Workout", back_populates="workout_exercises_association")


class Workout(Base):
    __tablename__ = "workouts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    scheduled_date = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    completion_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    pose_estimation_feedback = Column(JSON, nullable=True)  # Store CV feedback, perhaps keyed by WorkoutExercise.id

    user = relationship("User", back_populates="workouts")
    # This association allows a Workout to have many Exercises with specific details for that workout instance
    workout_exercises_association = relationship("WorkoutExercise", back_populates="workout",
                                                 cascade="all, delete-orphan")


class NutritionLog(Base):
    __tablename__ = "nutrition_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    food_item_name = Column(String, nullable=False)
    barcode = Column(String, index=True, nullable=True)
    calories = Column(Float, nullable=True)
    protein_g = Column(Float, nullable=True)
    carbs_g = Column(Float, nullable=True)
    fat_g = Column(Float, nullable=True)
    micronutrients = Column(JSON, nullable=True)
    serving_size = Column(String, nullable=True)
    meal_type = Column(String, nullable=True)
    consumed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="nutrition_logs")


class SleepRecord(Base):
    __tablename__ = "sleep_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    total_duration_minutes = Column(Float, nullable=True)
    deep_sleep_minutes = Column(Float, nullable=True)
    light_sleep_minutes = Column(Float, nullable=True)
    rem_sleep_minutes = Column(Float, nullable=True)
    awake_minutes = Column(Float, nullable=True)
    sleep_score = Column(Float, nullable=True)
    hrv_during_sleep = Column(Float, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)  # Added for tracking when record was created

    user = relationship("User", back_populates="sleep_records")


class PaymentRecord(Base):
    __tablename__ = "payment_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    consultation_booking_id = Column(Integer, nullable=True)  # Link to a future "ConsultationBooking" table
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="usd")
    payment_gateway = Column(SAEnum(PaymentGatewayDB), nullable=False)
    transaction_id = Column(String, unique=True, index=True, nullable=True)  # From payment provider
    status = Column(SAEnum(PaymentStatusDB), nullable=False, default=PaymentStatusDB.PENDING)
    payment_intent_id = Column(String, index=True, nullable=True)  # For Stripe
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="payment_records")

# --- Conceptual Future Models (Not fully implemented in CRUD/routes for brevity) ---
# These would be defined similarly if fully integrated.
# Example:
# class GeneticDataUploadRecord(Base):
#     __tablename__ = "genetic_data_uploads"
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     provider = Column(String, nullable=False)
#     file_path_secure = Column(String, nullable=False) # Path to encrypted stored file
#     uploaded_at = Column(DateTime, default=datetime.utcnow)
#     status = Column(String, default="pending_analysis") # e.g., pending_analysis, processing, completed, error
#     report_summary_id = Column(Integer, ForeignKey("genetic_reports.id"), nullable=True)
#     user = relationship("User", back_populates="genetic_data_uploads")

# class MentalWellnessDBLog(Base): # To avoid conflict with Pydantic schema name
#      __tablename__ = "mental_wellness_logs"
#      id = Column(Integer, primary_key=True, index=True)
#      user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#      log_type = Column(String, nullable=False) # From MentalWellnessLogType enum
#      value_numeric = Column(Float, nullable=True)
#      value_text = Column(String, nullable=True)
#      duration_seconds = Column(Integer, nullable=True)
#      notes = Column(String, nullable=True)
#      logged_at = Column(DateTime, default=datetime.utcnow)
#      user = relationship("User", back_populates="mental_wellness_logs")