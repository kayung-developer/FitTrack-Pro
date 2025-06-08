from backend import models, schemas
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

# --- CONCEPTUAL Telehealth Service ---

def get_available_trainers(db: Session, specialty_filter: Optional[str] = None) -> List[schemas.TrainerProfile]:
    """
    CONCEPTUAL: Fetches a list of available trainers.
    In a real system, trainers would have profiles and schedules stored in the DB.
    """
    print(f"Conceptual Telehealth: Fetching trainers. Specialty filter: {specialty_filter}")
    # Mocked data
    mock_trainers = [
        schemas.TrainerProfile(trainer_id=1, name="Dr. Alex Fitwell", specialties=["nutrition", "strength_training"], availability_slots=[datetime.utcnow() + timedelta(days=1, hours=h) for h in range(2, 5)]),
        schemas.TrainerProfile(trainer_id=2, name="Coach Sarah Strong", specialties=[" HIIT", "endurance_running"], availability_slots=[datetime.utcnow() + timedelta(days=2, hours=h) for h in range(1, 4)]),
        schemas.TrainerProfile(trainer_id=3, name="Yogi Master Zen", specialties=["yoga", "meditation", "mental_wellness"], availability_slots=[datetime.utcnow() + timedelta(days=1, hours=h) for h in [1, 3, 5]]),
    ]
    if specialty_filter:
        return [t for t in mock_trainers if specialty_filter.lower() in [s.lower() for s in t.specialties]]
    return mock_trainers

def book_telehealth_session_service(
    db: Session,
    user: models.User,
    booking_request: schemas.TelehealthBookingRequest
) -> schemas.TelehealthBookingResponse:
    """
    CONCEPTUAL: Books a telehealth session.
    This would involve:
    - Checking trainer availability for the requested slot.
    - Creating a meeting link (e.g., via Zoom API, Jitsi Meet, Google Meet API).
    - Saving the booking to a 'TelehealthBookings' table in the DB.
    - Notifying user and trainer.
    """
    print(f"Conceptual Telehealth: Booking session for user {user.id} with trainer {booking_request.trainer_id}")
    print(f"  Slot: {booking_request.slot_datetime}, Service: {booking_request.service_type}")

    # 1. Validate trainer_id and slot_datetime against trainer's actual availability.
    #    (Fetch trainer from DB, check their schedule)
    #    For now, assume slot is valid.

    # 2. Generate a unique booking ID and meeting URL.
    booking_id = f"TELEHEALTH_{user.id}_{booking_request.trainer_id}_{int(booking_request.slot_datetime.timestamp())}"
    # Example meeting URL generation (replace with actual video conferencing API call)
    meeting_url = f"https://meet.jit.si/FitTrackPro_{booking_id}" # Jitsi Meet example

    # 3. Save to DB (conceptual model: models.TelehealthBooking)
    #    db_booking = models.TelehealthBooking(
    #        id=booking_id, user_id=user.id, trainer_id=booking_request.trainer_id,
    #        slot_datetime=booking_request.slot_datetime, service_type=booking_request.service_type,
    #        meeting_url=meeting_url, status="confirmed", notes_for_trainer=booking_request.user_notes_for_trainer
    #    )
    #    db.add(db_booking); db.commit()

    # 4. (Optional) Send email/notifications to user and trainer.

    # Mock trainer name
    trainer_name = f"Trainer {booking_request.trainer_id}"
    mock_trainers = get_available_trainers(db) # Use existing mock function
    found_trainer = next((t for t in mock_trainers if t.trainer_id == booking_request.trainer_id), None)
    if found_trainer:
        trainer_name = found_trainer.name


    return schemas.TelehealthBookingResponse(
        booking_id=booking_id,
        meeting_url=meeting_url,
        confirmation_details=f"Your {booking_request.service_type} session with {trainer_name} is confirmed for {booking_request.slot_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')}.",
        trainer_name=trainer_name,
        booked_slot=booking_request.slot_datetime
    )

def get_user_telehealth_bookings(db: Session, user: models.User) -> List[schemas.TelehealthBookingResponse]:
    """CONCEPTUAL: Fetches past and upcoming telehealth bookings for a user."""
    print(f"Conceptual Telehealth: Fetching bookings for user {user.id}")
    # Fetch from DB:
    # db_bookings = db.query(models.TelehealthBooking).filter_by(user_id=user.id).order_by(models.TelehealthBooking.slot_datetime.desc()).all()
    # return [schemas.TelehealthBookingResponse.from_orm(b) for b in db_bookings]

    # Mocked data:
    return [
        schemas.TelehealthBookingResponse(
            booking_id=f"TELEHEALTH_{user.id}_1_OLD", meeting_url="https://meet.jit.si/OldSession",
            confirmation_details="Past session: Nutrition check-up", trainer_name="Dr. Alex Fitwell",
            booked_slot=datetime.utcnow() - timedelta(days=7)
        )
    ]