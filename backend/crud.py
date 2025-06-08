from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List, Optional, Type, TypeVar, Generic, Any, Dict, Union
from pydantic import BaseModel as PydanticBaseModel  # Alias for clarity


from backend import models
from backend import schemas as pydantic_schemas  # Consistent alias
from backend.core.security import get_password_hash
from backend.database import Base as DBBase  # SQLAlchemy Base

# --- Generic CRUD Base ---
ModelType = TypeVar("ModelType", bound=DBBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=PydanticBaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=PydanticBaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = obj_in.dict()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:  # Catch potential unique constraint violations etc.
            db.rollback()
            raise e
        return db_obj

    def update(
            self, db: Session, *, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        obj_data = db_obj.__dict__  # Get current attributes
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)  # Pydantic schema to dict

        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:
            db.rollback()
            raise e
        return db_obj

    def remove(self, db: Session, *, id: int) -> Optional[ModelType]:
        obj = db.query(self.model).get(id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj


# --- User CRUD ---
class CRUDUser(CRUDBase[models.User, pydantic_schemas.UserCreate, pydantic_schemas.UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[models.User]:
        return db.query(models.User).filter(models.User.email == email).first()

    def get_by_firebase_uid(self, db: Session, *, firebase_uid: str) -> Optional[models.User]:  # New method
        return db.query(models.User).filter(models.User.firebase_uid == firebase_uid).first()

    def create(self, db: Session, *, obj_in: pydantic_schemas.UserCreate) -> models.User:
        # This is for the old email/password registration.
        # If Firebase is primary, this might be deprecated or used for admin creation.
        print(f"CRUD DEBUG: Standard user creation for email: {obj_in.email}")
        hashed_password = get_password_hash(obj_in.password)
        db_obj = models.User(
            email=obj_in.email,
            hashed_password=hashed_password,  # Password still stored for this path
            full_name=obj_in.full_name,
            age=obj_in.age,
            weight_kg=obj_in.weight_kg,
            height_cm=obj_in.height_cm,
            fitness_goals=obj_in.fitness_goals,
            is_active=True
        )
        # ... (commit, refresh, error handling as before) ...
        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:
            db.rollback();
            raise e
        except SQLAlchemyError as e:
            db.rollback();
            raise e
        except Exception as e:
            db.rollback();
            raise e
        return db_obj

    def create_with_firebase(self, db: Session, *,
                             obj_in: pydantic_schemas.UserCreateFirebase) -> models.User:  # New method
        print(f"CRUD DEBUG: Creating user from Firebase data for email: {obj_in.email}, UID: {obj_in.firebase_uid}")
        db_obj = models.User(
            email=obj_in.email,
            firebase_uid=obj_in.firebase_uid,
            full_name=obj_in.full_name,
            is_active=True,
            # hashed_password can be None if only Firebase auth is used for this user
        )
        # ... (commit, refresh, error handling as before) ...
        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:  # Could happen if email or firebase_uid is not unique
            db.rollback()
            print(f"CRUD ERROR: IntegrityError creating Firebase user {obj_in.email}: {e}")
            # Attempt to fetch existing user if integrity error on unique constraint
            existing_user = self.get_by_firebase_uid(db, firebase_uid=obj_in.firebase_uid)
            if existing_user: return existing_user  # Already exists
            existing_user_by_email = self.get_by_email(db, email=obj_in.email)
            if existing_user_by_email:  # Email exists, maybe different UID - needs careful handling
                print(
                    f"Warning: Email {obj_in.email} exists but different Firebase UID. Linking might be complex here.")
                # For now, just re-raise or return the existing user by email if no UID was set
                if not existing_user_by_email.firebase_uid:
                    existing_user_by_email.firebase_uid = obj_in.firebase_uid
                    db.add(existing_user_by_email);
                    db.commit();
                    db.refresh(existing_user_by_email)
                    return existing_user_by_email
            raise e  # Re-raise if not resolved
        except SQLAlchemyError as e:
            db.rollback();
            print(f"CRUD ERROR: SQLAlchemyError creating Firebase user {obj_in.email}: {e}");
            raise e
        except Exception as e:
            db.rollback();
            print(f"CRUD ERROR: Exception creating Firebase user {obj_in.email}: {e}");
            raise e
        return db_obj

    def update(
            self, db: Session, *, db_obj: models.User, obj_in: Union[pydantic_schemas.UserUpdate, Dict[str, Any]]
    ) -> models.User:
        # ... (update logic as before, but note password might be None if Firebase is primary) ...
        # ... if password is in update_data and user also has firebase_uid, decide how to handle ...
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)

        if "password" in update_data and update_data["password"]:
            # Only hash and set password if it's provided and non-empty
            # This means if user primarily uses Firebase, their local password can remain None
            # Or, you might decide to disallow password updates if firebase_uid is set.
            hashed_password = get_password_hash(update_data["password"])
            db_obj.hashed_password = hashed_password
            del update_data["password"]

        return super().update(db, db_obj=db_obj, obj_in=update_data)


user = CRUDUser(models.User)


# --- HealthMetric CRUD ---
class CRUDHealthMetric(
    CRUDBase[models.HealthMetric, pydantic_schemas.HealthMetricCreate, pydantic_schemas.HealthMetricUpdate]):
    def get_by_user_id(self, db: Session, *, user_id: int) -> Optional[models.HealthMetric]:
        return db.query(models.HealthMetric).filter(models.HealthMetric.user_id == user_id).first()

    def create_with_user(self, db: Session, *, obj_in: pydantic_schemas.HealthMetricCreate,
                         user_id: int) -> models.HealthMetric:
        obj_in_data = obj_in.dict()
        db_obj = self.model(**obj_in_data, user_id=user_id)
        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:
            db.rollback()
            raise e
        return db_obj


health_metric = CRUDHealthMetric(models.HealthMetric)


# --- Activity CRUD ---
class CRUDActivity(CRUDBase[models.Activity, pydantic_schemas.ActivityCreate, pydantic_schemas.ActivityUpdate]):
    def get_multi_by_user(self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100) -> List[models.Activity]:
        return db.query(self.model).filter(models.Activity.user_id == user_id).order_by(
            models.Activity.start_time.desc()).offset(skip).limit(limit).all()

    def create_with_user(self, db: Session, *, obj_in: pydantic_schemas.ActivityCreate,
                         user_id: int) -> models.Activity:
        obj_in_data = obj_in.dict()
        db_obj = self.model(**obj_in_data, user_id=user_id)
        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:
            db.rollback()
            raise e
        return db_obj


activity = CRUDActivity(models.Activity)


# --- Exercise CRUD ---
class CRUDExercise(CRUDBase[models.Exercise, pydantic_schemas.ExerciseCreate, pydantic_schemas.ExerciseUpdate]):
    def get_by_name(self, db: Session, *, name: str) -> Optional[models.Exercise]:
        return db.query(models.Exercise).filter(models.Exercise.name == name).first()


exercise = CRUDExercise(models.Exercise)


# --- Workout CRUD ---
class CRUDWorkout(CRUDBase[models.Workout, pydantic_schemas.WorkoutCreate, pydantic_schemas.WorkoutUpdate]):
    def create_with_user(self, db: Session, *, obj_in: pydantic_schemas.WorkoutCreate, user_id: int) -> models.Workout:
        workout_data = obj_in.dict(exclude={"workout_exercises"})
        db_workout = models.Workout(**workout_data, user_id=user_id)

        for wo_exercise_in in obj_in.workout_exercises:
            # exercise_obj = db.query(models.Exercise).get(wo_exercise_in.exercise_id) # Ensure exercise exists
            # if not exercise_obj: continue # Or raise error
            db_wo_exercise = models.WorkoutExercise(**wo_exercise_in.dict())  # exercise_id is already in wo_exercise_in
            db_workout.workout_exercises_association.append(db_wo_exercise)

        db.add(db_workout)
        try:
            db.commit()
            db.refresh(db_workout)
        except IntegrityError as e:
            db.rollback()
            raise e
        return db_workout

    def get_multi_by_user(self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100) -> List[models.Workout]:
        return db.query(self.model).filter(models.Workout.user_id == user_id).order_by(
            models.Workout.scheduled_date.desc()).offset(skip).limit(limit).all()

    def update(self, db: Session, *, db_obj: models.Workout, obj_in: pydantic_schemas.WorkoutUpdate) -> models.Workout:
        update_data = obj_in.dict(exclude_unset=True, exclude={"workout_exercises"})

        # Update scalar fields
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        # Handle workout_exercises update (if provided)
        if obj_in.workout_exercises is not None:
            # Simple strategy: delete all existing and add new ones
            # For more complex updates (preserving IDs, partial mods), more logic is needed
            for existing_wo_exercise in db_obj.workout_exercises_association:
                db.delete(existing_wo_exercise)
            db.flush()  # Process deletes before adds if in same transaction phase

            new_wo_exercises_assoc = []
            for wo_exercise_in in obj_in.workout_exercises:
                # Ensure exercise_id is present
                if wo_exercise_in.exercise_id is None: continue  # Or raise error

                # exercise_obj = db.query(models.Exercise).get(wo_exercise_in.exercise_id)
                # if not exercise_obj: continue # Or raise error

                # Convert Pydantic schema to dict for WorkoutExercise model
                if isinstance(wo_exercise_in, pydantic_schemas.WorkoutExerciseCreate) or isinstance(wo_exercise_in,
                                                                                                    pydantic_schemas.WorkoutExerciseUpdate):
                    new_wo_exercise_db = models.WorkoutExercise(**wo_exercise_in.dict(exclude_unset=True),
                                                                workout_id=db_obj.id)
                    new_wo_exercises_assoc.append(new_wo_exercise_db)
            db_obj.workout_exercises_association = new_wo_exercises_assoc

        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:
            db.rollback()
            raise e
        return db_obj


workout = CRUDWorkout(models.Workout)


# --- NutritionLog CRUD ---
class CRUDNutritionLog(
    CRUDBase[models.NutritionLog, pydantic_schemas.NutritionLogCreate, pydantic_schemas.NutritionLogUpdate]):
    def get_multi_by_user(self, db: Session, *, user_id: int, date_filter: Optional[datetime.date] = None,
                          skip: int = 0, limit: int = 100) -> List[models.NutritionLog]:
        query = db.query(self.model).filter(models.NutritionLog.user_id == user_id)
        if date_filter:
            start_datetime = datetime.combine(date_filter, datetime.min.time())
            end_datetime = datetime.combine(date_filter, datetime.max.time())
            query = query.filter(models.NutritionLog.consumed_at >= start_datetime,
                                 models.NutritionLog.consumed_at <= end_datetime)
        return query.order_by(models.NutritionLog.consumed_at.desc()).offset(skip).limit(limit).all()

    def create_with_user(self, db: Session, *, obj_in: pydantic_schemas.NutritionLogCreate,
                         user_id: int) -> models.NutritionLog:
        obj_in_data = obj_in.dict()
        db_obj = self.model(**obj_in_data, user_id=user_id)
        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:
            db.rollback()
            raise e
        return db_obj


nutrition_log = CRUDNutritionLog(models.NutritionLog)


# --- SleepRecord CRUD ---
class CRUDSleepRecord(
    CRUDBase[models.SleepRecord, pydantic_schemas.SleepRecordCreate, pydantic_schemas.SleepRecordUpdate]):
    def get_multi_by_user(self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100) -> List[
        models.SleepRecord]:
        return db.query(self.model).filter(models.SleepRecord.user_id == user_id).order_by(
            models.SleepRecord.start_time.desc()).offset(skip).limit(limit).all()

    def create_with_user(self, db: Session, *, obj_in: pydantic_schemas.SleepRecordCreate,
                         user_id: int) -> models.SleepRecord:
        obj_in_data = obj_in.dict()
        db_obj = self.model(**obj_in_data, user_id=user_id)
        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:
            db.rollback()
            raise e
        return db_obj


sleep_record = CRUDSleepRecord(models.SleepRecord)


# --- PaymentRecord CRUD ---
class CRUDPaymentRecord(
    CRUDBase[models.PaymentRecord, PydanticBaseModel, PydanticBaseModel]):  # Schemas handled by service
    def get_by_payment_intent_id(self, db: Session, *, payment_intent_id: str) -> Optional[models.PaymentRecord]:
        return db.query(models.PaymentRecord).filter(
            models.PaymentRecord.payment_intent_id == payment_intent_id).first()

    def get_by_transaction_id(self, db: Session, *, transaction_id: str) -> Optional[models.PaymentRecord]:
        return db.query(models.PaymentRecord).filter(models.PaymentRecord.transaction_id == transaction_id).first()

    def get_multi_by_user(self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100) -> List[
        models.PaymentRecord]:
        return db.query(self.model).filter(models.PaymentRecord.user_id == user_id).order_by(
            models.PaymentRecord.created_at.desc()).offset(skip).limit(limit).all()

    def create_payment(self, db: Session, *, user_id: int, amount: float, currency: str,
                       gateway: models.PaymentGatewayDB, status: models.PaymentStatusDB,
                       transaction_id: Optional[str] = None, payment_intent_id: Optional[str] = None,
                       consultation_booking_id: Optional[int] = None) -> models.PaymentRecord:
        db_obj = models.PaymentRecord(
            user_id=user_id,
            amount=amount,
            currency=currency,
            payment_gateway=gateway,
            transaction_id=transaction_id,
            status=status,
            payment_intent_id=payment_intent_id,
            consultation_booking_id=consultation_booking_id
        )
        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:
            db.rollback()
            raise e
        return db_obj

    def update_status(self, db: Session, *, db_obj: models.PaymentRecord, status: models.PaymentStatusDB,
                      transaction_id: Optional[str] = None) -> models.PaymentRecord:
        db_obj.status = status
        if transaction_id:
            db_obj.transaction_id = transaction_id
        db.add(db_obj)
        try:
            db.commit()
            db.refresh(db_obj)
        except IntegrityError as e:
            db.rollback()
            raise e
        return db_obj


payment_record = CRUDPaymentRecord(models.PaymentRecord)