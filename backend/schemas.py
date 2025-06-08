from pydantic import BaseModel, EmailStr, Field, HttpUrl, ConfigDict # Import ConfigDict
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import enum

# --- Enums used in Schemas (mirroring models.py enums) ---
class ActivityTypeSchema(str, enum.Enum):
    RUNNING = "running"
    CYCLING = "cycling"
    WALKING = "walking"
    SWIMMING = "swimming"
    STRENGTH_TRAINING = "strength_training"
    HIIT = "hiit"
    YOGA = "yoga"
    OTHER = "other"

class PaymentStatusSchema(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentGatewaySchema(str, enum.Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    CRYPTO = "crypto"
    MASTERCARD_VISA_VERVE = "card"

# --- Base Schemas with Config ---
class OrmBaseModel(BaseModel):
    class Config:
        orm_mode = True

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    age: Optional[int] = Field(None, gt=0, lt=120)
    weight_kg: Optional[float] = Field(None, gt=0)
    height_cm: Optional[float] = Field(None, gt=0)
    fitness_goals: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(UserBase):
    password: Optional[str] = Field(None, min_length=8)


class UserCreateFirebase(BaseModel): # New schema
    email: EmailStr
    firebase_uid: str
    full_name: Optional[str] = None
    # Other fields like age, weight, etc., are optional at this point
    # and can be updated via the profile page.

class UserSchema(OrmBaseModel, UserBase): # UserBase does not have firebase_uid
    id: int
    firebase_uid: Optional[str] = None # Add firebase_uid here
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # UserBase itself doesn't include firebase_uid, so it's added directly to UserSchema
# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# --- HealthMetric Schemas ---
class HealthMetricBase(BaseModel):
    bmi: Optional[float] = None
    body_fat_percentage: Optional[float] = Field(None, ge=0, le=100)
    bmr: Optional[float] = None # Basal Metabolic Rate
    tdee: Optional[float] = None # Total Daily Energy Expenditure
    hrv: Optional[float] = None # Heart Rate Variability

class HealthMetricCreate(HealthMetricBase):
    user_id: Optional[int] = None # Will be set by current_user logic

class HealthMetricUpdate(HealthMetricBase): # For partial updates
    pass

class HealthMetricSchema(OrmBaseModel, HealthMetricBase):
    id: int
    user_id: int
    recorded_at: datetime

# --- Activity Schemas ---
class GPSDataPoint(BaseModel):
    lat: float
    lon: float
    timestamp: datetime
    altitude: Optional[float] = None
    accuracy: Optional[float] = None

class ActivityBase(BaseModel):
    activity_type: ActivityTypeSchema
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[float] = Field(None, ge=0)
    distance_km: Optional[float] = Field(None, ge=0)
    calories_burned: Optional[float] = Field(None, ge=0)
    avg_heart_rate: Optional[int] = Field(None, ge=0)
    max_heart_rate: Optional[int] = Field(None, ge=0)
    hr_zones: Optional[Dict[str, float]] = None # e.g., {"zone1_time_mins": 10, "zone2_time_mins": 20}
    gps_data: Optional[List[GPSDataPoint]] = None
    notes: Optional[str] = None

class ActivityCreate(ActivityBase):
    pass

class ActivityUpdate(ActivityBase): # For partial updates
    activity_type: Optional[ActivityTypeSchema] = None
    start_time: Optional[datetime] = None
    # All fields optional for update

class ActivitySchema(OrmBaseModel, ActivityBase):
    id: int
    user_id: int
    created_at: datetime

# --- Exercise Schemas ---
class ExerciseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    target_muscles: Optional[str] = None # Comma-separated or JSON array
    equipment_needed: Optional[str] = None
    # video_url: Optional[HttpUrl] = None

class ExerciseCreate(ExerciseBase):
    pass

class ExerciseUpdate(ExerciseBase): # For partial updates
    name: Optional[str] = Field(None, min_length=1, max_length=100)

class ExerciseSchema(OrmBaseModel, ExerciseBase):
    id: int

# --- WorkoutExercise Schemas ---
class WorkoutExerciseBase(BaseModel):
    exercise_id: int
    sets: Optional[int] = Field(None, ge=0)
    reps: Optional[str] = None # e.g., "8-12" or "AMRAP" or "15"
    weight_kg: Optional[float] = Field(None, ge=0)
    rest_seconds: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None

class WorkoutExerciseCreate(WorkoutExerciseBase):
    pass

class WorkoutExerciseUpdate(WorkoutExerciseBase): # For partial updates
    exercise_id: Optional[int] = None

class WorkoutExerciseSchema(OrmBaseModel, WorkoutExerciseBase):
    id: int
    exercise: ExerciseSchema # Nested schema for details

# --- Workout Schemas ---
class WorkoutBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    scheduled_date: Optional[datetime] = None

class WorkoutCreate(WorkoutBase):
    workout_exercises: List[WorkoutExerciseCreate] = []

class WorkoutUpdate(WorkoutBase): # For partial updates
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_completed: Optional[bool] = None
    # Allow updating exercises; might need more granular control (add/remove/update specific exercise)
    workout_exercises: Optional[List[Union[WorkoutExerciseUpdate, WorkoutExerciseCreate]]] = None
    pose_estimation_feedback: Optional[Dict[str, Any]] = None # Updateable feedback

class WorkoutSchema(OrmBaseModel, WorkoutBase):
    id: int
    user_id: int
    is_completed: bool
    completion_date: Optional[datetime] = None
    created_at: datetime
    workout_exercises: List[WorkoutExerciseSchema] = []
    pose_estimation_feedback: Optional[Dict[str, Any]] = None

# --- NutritionLog Schemas ---
class NutritionLogBase(BaseModel):
    food_item_name: str = Field(..., min_length=1, max_length=200)
    barcode: Optional[str] = None
    calories: Optional[float] = Field(None, ge=0)
    protein_g: Optional[float] = Field(None, ge=0)
    carbs_g: Optional[float] = Field(None, ge=0)
    fat_g: Optional[float] = Field(None, ge=0)
    micronutrients: Optional[Dict[str, Any]] = None # e.g., {"vitamin_c_mg": 50, "iron_mg": 5}
    serving_size: Optional[str] = None
    meal_type: Optional[str] = Field(None, description="e.g., Breakfast, Lunch, Dinner, Snack")
    consumed_at: datetime = Field(default_factory=datetime.utcnow)

class NutritionLogCreate(NutritionLogBase):
    pass

class NutritionLogUpdate(NutritionLogBase): # For partial updates
    food_item_name: Optional[str] = Field(None, min_length=1, max_length=200)
    consumed_at: Optional[datetime] = None

class NutritionLogSchema(OrmBaseModel, NutritionLogBase):
    id: int
    user_id: int

# --- SleepRecord Schemas ---
class SleepRecordBase(BaseModel):
    start_time: datetime
    end_time: datetime
    total_duration_minutes: Optional[float] = Field(None, ge=0)
    deep_sleep_minutes: Optional[float] = Field(None, ge=0)
    light_sleep_minutes: Optional[float] = Field(None, ge=0)
    rem_sleep_minutes: Optional[float] = Field(None, ge=0)
    awake_minutes: Optional[float] = Field(None, ge=0)
    sleep_score: Optional[float] = Field(None, ge=0, le=100) # 0-100
    hrv_during_sleep: Optional[float] = None
    notes: Optional[str] = None

class SleepRecordCreate(SleepRecordBase):
    pass

class SleepRecordUpdate(SleepRecordBase): # For partial updates
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class SleepRecordSchema(OrmBaseModel, SleepRecordBase):
    id: int
    user_id: int

# --- Payment Schemas ---
class PaymentIntentCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Amount in major currency unit, e.g., USD dollars")
    currency: str = Field("usd", min_length=3, max_length=3)
    consultation_type: str # e.g., "30_min_nutrition_coaching" or service ID

class PaymentIntentResponse(BaseModel):
    client_secret: str # For Stripe
    payment_intent_id: str
    publishable_key: str

class PaypalOrderCreate(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field("usd", min_length=3, max_length=3)
    consultation_type: str

class PaypalOrderResponse(BaseModel):
    order_id: str
    approve_url: HttpUrl # URL for user to approve payment on PayPal

class CryptoPaymentRequest(BaseModel):
    amount_crypto: float = Field(..., gt=0)
    crypto_currency: str # e.g. "BTC", "ETH"
    consultation_type: str

class CryptoPaymentResponse(BaseModel):
    payment_address: str
    qr_code_url: Optional[HttpUrl] = None # URL to a QR code image for the address
    status_check_url: HttpUrl # URL to poll for payment confirmation or link to explorer

class PaymentRecordSchema(OrmBaseModel):
    id: int
    user_id: int
    consultation_booking_id: Optional[int] = None
    amount: float
    currency: str
    payment_gateway: PaymentGatewaySchema
    transaction_id: Optional[str] = None
    status: PaymentStatusSchema
    payment_intent_id: Optional[str] = None # For Stripe
    created_at: datetime
    updated_at: datetime

# --- General response model ---
class Message(BaseModel):
    message: str

# --- CV (Pose Estimation) Schemas ---
class PoseEstimationRequest(BaseModel):
    exercise_type: str
    video_frames_base64: List[str] = Field(..., min_items=1) # List of base64 encoded image frames

class PoseEstimationFeedback(BaseModel):
    exercise_type_analyzed: str
    frames_processed: int
    form_score: float = Field(ge=0, le=1)
    corrective_feedback: List[str]
    key_metrics_summary: Optional[Dict[str, Any]] = None # e.g., min/max angles

# --- External API Schemas (for responses from nutrition_service) ---
class USDANutrient(BaseModel):
    nutrientName: str
    value: float
    unitName: str

class USDAFoodItem(BaseModel):
    description: str
    fdcId: int
    brandOwner: Optional[str] = None
    ingredients: Optional[str] = None
    foodNutrients: List[USDANutrient] = []

class OpenFoodFactsNutriments(BaseModel):
    # Add relevant fields from OpenFoodFacts, e.g.:
    energy_kcal_100g: Optional[float] = Field(None, alias="energy-kcal_100g")
    proteins_100g: Optional[float] = None
    carbohydrates_100g: Optional[float] = None
    fat_100g: Optional[float] = None
    # ... many more possible fields

class OpenFoodFactsProduct(BaseModel):
    product_name: Optional[str] = None
    brands: Optional[str] = None
    nutriments: Optional[OpenFoodFactsNutriments] = None
    ingredients_text: Optional[str] = None
    image_front_url: Optional[HttpUrl] = None

class BarcodeLookupResponse(BaseModel):
    status: Optional[int] = None # 1 if product found
    product: Optional[OpenFoodFactsProduct] = None
    message: Optional[str] = None # For errors or not found
    error: Optional[str] = None # Added for error structure
    details: Optional[str] = None

class FoodDBSearchResponseItem(BaseModel): # Could be USDAFoodItem or another structure
    description: str
    source_id: str # e.g. FDC ID
    details: Dict[str, Any] # Raw details or parsed nutrients

class FoodDBSearchResponse(BaseModel):
    query: str
    source: str
    results: List[FoodDBSearchResponseItem]
    error: Optional[str] = None
    message: Optional[str] = None

# --- Future Advancement Schemas (Conceptual Placeholders) ---

# 1. AI & Predictive Health Modeling
class AIPredictionRequest(BaseModel):
    user_id: int # Often derived from token, but can be explicit for admin/batch jobs
    # Example inputs, can be much more complex
    recent_activity_data: Optional[List[ActivitySchema]] = None
    current_health_metrics: Optional[HealthMetricSchema] = None
    movement_data_stream_id: Optional[str] = None # For real-time analysis from a sensor stream

class AIPredictionResponse(BaseModel):
    injury_risk_assessment: Optional[Dict[str, float]] = None # e.g., {"knee_ligament_strain": 0.65}
    preventive_suggestions: Optional[List[str]] = None
    adaptive_plan_adjustments: Optional[Dict[str, Any]] = None # e.g., {"reduce_running_volume_by_percent": 20}
    performance_forecast: Optional[Dict[str, Any]] = None # e.g., {"predicted_5k_time_improvement_percent": 5}

# 2. 3D & AR/VR Integration
class ARVRGuidanceRequest(BaseModel):
    user_id: int
    exercise_id: int # Link to an ExerciseSchema
    environment_preference: Optional[str] = "gym_default" # e.g., "outdoor_run", "fantasy_world"
    session_type: str = "realtime_feedback" # "guided_workout", "simulation"

class ARVRGuidanceResponse(BaseModel):
    session_id: str
    connection_details: Dict[str, Any] # e.g., server IP, port for VR stream, WebRTC config
    virtual_environment_url: Optional[HttpUrl] = None
    avatar_customization_options: Optional[Dict[str, Any]] = None

# 3. IoT & Smart Gym Equipment Sync
class IoTDeviceRegistration(BaseModel):
    user_id: int
    device_id: str # Unique identifier of the smart equipment
    device_type: str # e.g., "treadmill", "smart_dumbbells", "rowing_machine"
    manufacturer: Optional[str] = None
    model: Optional[str] = None

class IoTDeviceData(BaseModel):
    device_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data_type: str # e.g., "treadmill_speed_kmh", "smart_weight_reps", "power_watts"
    value: Any # Can be float, int, dict for complex data
    unit: Optional[str] = None

# 4. Mental Wellness & Biofeedback
class MentalWellnessLogType(str, enum.Enum):
    MOOD = "mood"
    STRESS_LEVEL = "stress_level"
    MEDITATION_SESSION = "meditation_session"
    BREATHING_EXERCISE = "breathing_exercise"

class MentalWellnessLogCreate(BaseModel):
    user_id: Optional[int] = None # from token
    log_type: MentalWellnessLogType
    value_numeric: Optional[float] = None # e.g., mood score 1-10, stress level 1-10
    value_text: Optional[str] = None # e.g., "Anxious", "Calm"
    duration_seconds: Optional[int] = None # For sessions
    notes: Optional[str] = None
    logged_at: datetime = Field(default_factory=datetime.utcnow)
    # Potentially link to HRV data or facial expression analysis ID if available

class MentalWellnessLogSchema(OrmBaseModel, MentalWellnessLogCreate):
    id: int

# 5. Telehealth & Trainer Live Support
class TrainerProfile(BaseModel): # Simplified
    trainer_id: int
    name: str
    specialties: List[str]
    availability_slots: List[datetime] # Could be more complex (e.g., recurring)

class TelehealthBookingRequest(BaseModel):
    user_id: Optional[int] = None # from token
    trainer_id: int
    slot_datetime: datetime
    service_type: str # e.g., "video_coaching_30min", "fitness_assessment_checkup"
    user_notes_for_trainer: Optional[str] = None

class TelehealthBookingResponse(BaseModel):
    booking_id: str
    meeting_url: HttpUrl # e.g., Zoom, Jitsi, Google Meet link
    confirmation_details: str
    trainer_name: str
    booked_slot: datetime

# 6. Genetic & Epigenetic Fitness Insights
class GeneticDataUpload(BaseModel): # This would be a multipart form typically
    # user_id from token
    provider: str # e.g., "23andMe", "AncestryDNA", "Nebula"
    raw_data_format: str # e.g., "txt", "csv", "vcf"
    consent_given: bool = Field(..., description="Explicit consent for processing sensitive genetic data")
    # File itself handled by UploadFile in endpoint

class GeneticReportSummary(BaseModel):
    report_id: str
    user_id: int
    generated_at: datetime
    key_insights: Dict[str, Any] # e.g., {"endurance_potential": "high", "caffeine_metabolism": "slow"}
    dietary_recommendations: List[str]
    exercise_type_suitability: List[str]

# 7. Blockchain for Fitness Data Security
class BlockchainTransactionRequest(BaseModel):
    user_id: Optional[int] = None # from token
    transaction_type: str # "data_ownership_registration", "reward_claim", "nft_mint_achievement"
    data_to_hash: Optional[Dict[str, Any]] = None # For data registration
    achievement_id: Optional[str] = None # For rewards/NFTs
    nft_metadata_url: Optional[HttpUrl] = None # For NFT minting

class BlockchainTransactionResponse(BaseModel):
    transaction_hash: str # On-chain transaction hash
    status: str # e.g., "pending_confirmation", "confirmed", "failed"
    explorer_url: Optional[HttpUrl] = None
    message: Optional[str] = None

# 8. Sustainability & Eco-Friendly Metrics
class ActivityCarbonFootprintRequest(BaseModel):
    activity_id: int # Link to an existing user activity
    transport_mode_to_activity_location: Optional[str] = None # e.g., "car_gasoline_small", "bicycle", "public_transport_bus"
    distance_to_location_km: Optional[float] = None

class ActivityCarbonFootprintResponse(BaseModel):
    activity_id: int
    activity_type: ActivityTypeSchema
    estimated_carbon_footprint_kg_co2e: float
    breakdown: Optional[Dict[str, float]] = None # e.g., {"activity_itself": 0.01, "transport": 0.5}
    suggestions_for_reduction: Optional[List[str]] = None

# --- Websocket Schemas (Example for real-time updates) ---
class WebSocketMessage(BaseModel):
    type: str # e.g., "hr_update", "workout_progress", "new_challenge_alert"
    payload: Dict[str, Any]

