from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend import schemas as pydantic_schemas  # Renamed to avoid confusion
from backend import models  # For User model type hint
from backend.database import get_db  # For dependency

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

from backend.core.firebase_init import get_current_firebase_user # Import the new dependency

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")
def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password: # Handle cases where user has no local password (Firebase only)
        return False
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)





def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Ensure 'exp' is a Unix timestamp (seconds since epoch)
    to_encode.update({"exp": int(expire.replace(tzinfo=timezone.utc).timestamp())})
    # Add 'iat' (issued at) claim
    to_encode.update({"iat": int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())})

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> models.User:
    from backend import crud  # Avoid circular import at module level

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = pydantic_schemas.TokenData(email=email)
    except JWTError as e:
        print(f"JWTError: {e}")  # Log the error for debugging
        raise credentials_exception

    user = crud.get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

# Optional: Role-based access (conceptual)
# def require_role(role_name: str):
#     async def role_checker(current_user: models.User = Depends(get_current_active_user)):
#         if role_name not in current_user.roles: # Assuming User model has a 'roles' field (e.g., JSON or relationship)
#             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted for this user role")
#         return current_user
#     return role_checker