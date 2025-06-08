from contextlib import asynccontextmanager

from httplib2 import Response
from streamlit import status
from fastapi import FastAPI, Depends, HTTPException, status as http_status,  APIRouter
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from backend.database import engine, Base, get_db
from backend.routers import (
    auth, users, activities, workouts,
    nutrition, sleep, payments, advanced
)
from backend.core.config import settings
from backend.core.firebase_init import initialize_firebase_app # Import the initializer

# Create database tables if they don't exist
# This should ideally be handled by a migration tool like Alembic in production
# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize Firebase Admin SDK on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("INFO: Application startup...")
    if not initialize_firebase_app():
        print("CRITICAL: Firebase Admin SDK failed to initialize. Some auth features may not work.")
    # Any other startup logic
    yield
    # Shutdown
    print("INFO: Application shutdown.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan # Add lifespan context manager
)

origins = ["*"]
print(f"DEBUG: Using EXTREMELY PERMISSIVE CORS origins = ['*']")

# CORS (Cross-Origin Resource Sharing)
if settings.BACKEND_CORS_ORIGINS:
    origins = [origin.strip() for origin in settings.BACKEND_CORS_ORIGINS.split(",")]
    print(f"Allowing CORS for origins: {origins}") # This should now show your :63342 port
else:
    origins = ["http://localhost:3000", "http://localhost:8080", "http://localhost:63342"] # Default if not set
    print(f"Warning: BACKEND_CORS_ORIGINS not set. Using default: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all standard methods
    allow_headers=["*"], # Allows all headers
)

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["Users & Health Metrics"])
app.include_router(activities.router, prefix=f"{settings.API_V1_PREFIX}/activities", tags=["Activity Tracking"])
app.include_router(workouts.router, prefix=f"{settings.API_V1_PREFIX}/workouts", tags=["Workouts & Exercises"])
app.include_router(nutrition.router, prefix=f"{settings.API_V1_PREFIX}/nutrition", tags=["Nutrition Logging"])
app.include_router(sleep.router, prefix=f"{settings.API_V1_PREFIX}/sleep", tags=["Sleep Monitoring"])
app.include_router(payments.router, prefix=f"{settings.API_V1_PREFIX}/payments", tags=["Payments & Consultations"])
app.include_router(advanced.router, prefix=f"{settings.API_V1_PREFIX}/advanced", tags=["Advanced & Next-Gen Features"])




router = APIRouter()

# --- AGGRESSIVE CORS DEBUGGING FOR OPTIONS ---
# This is a temporary measure to ensure OPTIONS requests get the right headers
# for these specific paths. This should ideally be handled entirely by CORSMiddleware.
@router.options("/register", include_in_schema=False)
async def options_register():
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    # Manually set all relevant CORS headers for the preflight
    # Use the origin that your browser is actually sending, e.g., 'http://localhost:63342'
    # or be very permissive for debugging
    response.headers["Access-Control-Allow-Origin"] = "*" # Or specific like "http://localhost:63342"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS, DELETE, PUT"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, X-Requested-With"
    response.headers["Access-Control-Allow-Credentials"] = "true" # If your frontend sends credentials
    response.headers["Access-Control-Max-Age"] = "86400" # Cache preflight for 1 day
    print("DEBUG: Manual OPTIONS handler for /register hit.")
    return response

@router.options("/me", include_in_schema=False)
async def options_me():
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.headers["Access-Control-Allow-Origin"] = "*" # Or specific "http://localhost:63342"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS, DELETE, PUT"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, X-Requested-With"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Max-Age"] = "86400"
    print("DEBUG: Manual OPTIONS handler for /me hit.")
    return response

@router.options("/login", include_in_schema=False) # Also for login, just in case
async def options_login():
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.headers["Access-Control-Allow-Origin"] = "*" # Or specific "http://localhost:63342"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS, DELETE, PUT"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, X-Requested-With"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Max-Age"] = "86400"
    print("DEBUG: Manual OPTIONS handler for /login hit.")
    return response
# --- END AGGRESSIVE CORS DEBUGGING ---





@app.get(f"{settings.API_V1_PREFIX}/healthcheck", tags=["Health Check"], status_code=http_status.HTTP_200_OK)
def health_check(db: Session = Depends(get_db)):
    """
    Performs a health check of the API, including database connectivity.
    """
    try:
        # Try a simple query to check DB connection
        db.execute("SELECT 1") # SQLAlchemy 1.x style, for 2.0 use text("SELECT 1")
        # from sqlalchemy import text # For SQLAlchemy 2.0
        # db.execute(text("SELECT 1"))
        return {"status": "ok", "message": "API is healthy and database connection is successful."}
    except Exception as e:
        print(f"Health check failed: Database connection error: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"API is unhealthy. Database connection error: {str(e)}"
        )

# Simple root endpoint
@app.get("/", tags=["Root"])
async def read_root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}!",
        "version": settings.PROJECT_VERSION,
        "docs_url": app.docs_url,
        "redoc_url": app.redoc_url,
        "openapi_url": app.openapi_url
    }