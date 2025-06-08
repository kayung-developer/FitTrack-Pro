# backend/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from backend import crud, models, schemas as pydantic_schemas
from backend.core import security
from backend.core.firebase_init import get_current_firebase_user
from backend.database import get_db
from backend.core.config import settings
from backend.services import user_service

router = APIRouter()


@router.post("/firebase-signin", response_model=pydantic_schemas.UserSchema)
async def firebase_signin(
        current_user: models.User = Depends(get_current_firebase_user),
        # This dependency handles token verification and user creation/retrieval
        db: Session = Depends(get_db)  # Ensure db session is available if health metrics update is needed
):
    """
    Client sends Firebase ID token in Authorization header.
    This endpoint verifies it, ensures local user exists (creates/links if not),
    and returns the local user profile.
    Essentially, this is the new "login" or "session creation" point.
    """
    print(
        f"DEBUG: Firebase sign-in successful for user: {current_user.email} (ID: {current_user.id}, Firebase UID: {current_user.firebase_uid})")

    # Optionally, update health metrics on sign-in if profile data allows
    if current_user.weight_kg and current_user.height_cm and current_user.age:
        try:
            user_service.update_or_create_user_derived_health_metrics(db, current_user)
            db.refresh(current_user)
        except Exception as e:
            print(
                f"DEBUG: Non-critical error updating health metrics on Firebase sign-in for user '{current_user.email}': {e}")

    return current_user

@router.get("/me", response_model=pydantic_schemas.UserSchema)
async def read_current_user_profile(
    current_user: models.User = Depends(get_current_firebase_user)
):
    return current_user

@router.post("/logout", status_code=status.HTTP_200_OK)
async def firebase_logout(
    # Optional: could take the token to blacklist it on server-side if you implement such a system,
    # but Firebase token revocation is more complex.
    # For now, just acknowledge.
    current_user: models.User = Depends(get_current_firebase_user) # Ensures only authenticated user can "logout"
):
    print(f"DEBUG: Logout endpoint hit by Firebase user: {current_user.email}")
    return {"message": "Logout acknowledged. Client should handle Firebase sign-out."}



@router.post("/register", response_model=pydantic_schemas.UserSchema, status_code=status.HTTP_201_CREATED)
def register_user(user_in: pydantic_schemas.UserCreate, db: Session = Depends(get_db)):
    print(f"DEBUG: Registration attempt for email: '{user_in.email}' with password length: {len(user_in.password)}")
    print(f"DEBUG: Full registration payload: {user_in.dict()}")

    db_user = crud.user.get_by_email(db, email=user_in.email)
    if db_user:
        print(f"DEBUG: Registration failed. Email '{user_in.email}' already registered.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    try:
        created_user = crud.user.create(db=db, obj_in=user_in)
        print(f"DEBUG: User '{created_user.email}' (ID: {created_user.id}) created successfully.")
        print(
            f"DEBUG: Stored hashed password (first 10 chars): {created_user.hashed_password[:10] if created_user.hashed_password else 'None'}")
    except Exception as e:
        print(f"DEBUG: CRITICAL - Error during user creation in CRUD: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating user: {e}")

    if created_user.weight_kg and created_user.height_cm and created_user.age:
        try:
            user_service.update_or_create_user_derived_health_metrics(db, created_user)
            db.refresh(created_user)  # Important to get updated relations if any
            print(f"DEBUG: Health metrics updated/created for user '{created_user.email}'.")
        except Exception as e:
            print(f"DEBUG: Non-critical error updating health metrics for user '{created_user.email}': {e}")
            # Non-critical error, so don't fail registration, but good to log.

    return created_user


@router.post("/login", response_model=pydantic_schemas.Token)
def login_for_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    print(f"DEBUG: Login attempt for username (email): '{form_data.username}'")
    print(f"DEBUG: Password received for login (length): {len(form_data.password) if form_data.password else 0}")

    user = crud.user.get_by_email(db, email=form_data.username)

    if not user:
        print(f"DEBUG: Login failed. User not found for email: '{form_data.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    print(f"DEBUG: User found for login: ID {user.id}, Email '{user.email}', Active: {user.is_active}")
    print(
        f"DEBUG: Stored hashed password (first 10 chars): {user.hashed_password[:10] if user.hashed_password else 'None'}")

    is_password_correct = security.verify_password(form_data.password, user.hashed_password)
    print(f"DEBUG: Password verification result for '{form_data.username}': {is_password_correct}")

    if not is_password_correct:
        print(f"DEBUG: Login failed. Password verification failed for user: '{form_data.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        print(f"DEBUG: Login failed. User '{form_data.username}' is inactive.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account.")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    print(f"DEBUG: Login successful. Access token generated for user: '{user.email}'.")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=pydantic_schemas.UserSchema)
async def read_users_me(current_user: models.User = Depends(security.get_current_active_user)):
    return current_user


# Conceptual logout - JWTs are stateless on server
@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout_user(
        current_user: models.User = Depends(security.get_current_active_user)):  # Require auth to "logout"
    print(f"DEBUG: Logout requested by user: {current_user.email}")
    # For JWT, logout is typically handled client-side by deleting the token.
    # Server-side, you might blacklist the token if using a more complex setup (e.g., with Redis).
    # This endpoint is mostly a convention.
    return {"message": "Logout successful. Please clear your token on client-side."}