# backend/core/firebase_init.py
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

from backend.core.config import settings
from backend import models, crud, schemas as pydantic_schemas  # For type hints and user creation
from backend.database import get_db  # To interact with DB for user creation/retrieval
from sqlalchemy.orm import Session

firebase_app_initialized = False


def initialize_firebase_app():
    global firebase_app_initialized
    if not firebase_app_initialized:
        service_account_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH
        if not service_account_path or not os.path.exists(service_account_path):
            print(f"CRITICAL ERROR: Firebase service account key file not found at path: {service_account_path}")
            print("Firebase Admin SDK NOT initialized. Firebase authentication will FAIL.")
            # You might choose to raise an exception here to prevent the app from starting
            # or let it run in a degraded mode if Firebase is optional for some parts.
            # raise FileNotFoundError(f"Firebase service account key not found: {service_account_path}")
            return False  # Indicate failure

        try:
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            firebase_app_initialized = True
            print("INFO: Firebase Admin SDK initialized successfully.")
            return True
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to initialize Firebase Admin SDK: {e}")
            # raise e # Or handle more gracefully
            return False
    return True  # Already initialized


# Call initialization on module load (or better, in FastAPI startup event)
# initialize_firebase_app() # Moved to main.py startup event

# Scheme for Bearer token (Firebase ID Token)
firebase_bearer_scheme = HTTPBearer(description="Firebase ID Token")


async def verify_firebase_token(
        token_cred: HTTPAuthorizationCredentials = Depends(firebase_bearer_scheme)
) -> dict:
    """
    Verifies Firebase ID token and returns decoded claims.
    """
    if not firebase_app_initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase Admin SDK not initialized. Cannot verify token."
        )

    id_token = token_cred.credentials
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except firebase_admin.auth.InvalidIdTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase ID token: {e}",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )
    except firebase_admin.auth.ExpiredIdTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Expired Firebase ID token: {e}",
            headers={"WWW-Authenticate": "Bearer error=\"expired_token\""},
        )
    except Exception as e:  # Catch other Firebase auth errors
        print(f"Error verifying Firebase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not verify Firebase ID token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_firebase_user(
        db: Session = Depends(get_db),
        decoded_token: dict = Depends(verify_firebase_token)
) -> models.User:
    """
    Dependency to get the current user based on a verified Firebase ID token.
    Creates or updates the user in the local database.
    """
    firebase_uid = decoded_token.get("uid")
    email = decoded_token.get("email")
    # name = decoded_token.get("name") # Firebase might provide 'name'
    # picture = decoded_token.get("picture") # Firebase might provide 'picture'

    if not firebase_uid or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase token missing UID or email."
        )

    user = crud.user.get_by_firebase_uid(db, firebase_uid=firebase_uid)

    if not user:
        # User authenticated with Firebase but doesn't exist in our DB yet.
        # Try to find by email first, in case they registered with email/pass before Firebase linking.
        user_by_email = crud.user.get_by_email(db, email=email)
        if user_by_email:
            # User exists by email, link Firebase UID to this existing user.
            print(f"DEBUG: Linking Firebase UID {firebase_uid} to existing user {email} (ID: {user_by_email.id})")
            user_by_email.firebase_uid = firebase_uid
            # Optionally update name/picture from Firebase if available and our model supports it
            # if name and not user_by_email.full_name: user_by_email.full_name = name
            db.add(user_by_email)
            db.commit()
            db.refresh(user_by_email)
            user = user_by_email
        else:
            # Create a new user in our database.
            print(f"DEBUG: Creating new local user for Firebase UID {firebase_uid}, Email: {email}")
            user_create_schema = pydantic_schemas.UserCreateFirebase(  # Need a new schema for this
                email=email,
                firebase_uid=firebase_uid,
                full_name=decoded_token.get("name"),  # Get name from token if available
                # age, weight, height, fitness_goals would be set later via profile update
            )
            user = crud.user.create_with_firebase(db, obj_in=user_create_schema)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User account is inactive.")

    return user