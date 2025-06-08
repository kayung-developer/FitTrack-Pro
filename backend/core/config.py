# backend/core/config.py
import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict  # <<< CORRECT IMPORT FOR PYDANTIC V2 SETTINGS
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "Advanced Fitness Tracker"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./fitness_tracker.db")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "fallback_secret_key_32_chars_long_CHANGE_ME_IMMEDIATELY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7))

    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "sk_test_YOUR_STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_YOUR_STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_YOUR_STRIPE_WEBHOOK_SECRET")

    PAYPAL_CLIENT_ID: str = os.getenv("PAYPAL_CLIENT_ID", "YOUR_PAYPAL_CLIENT_ID")
    PAYPAL_CLIENT_SECRET: str = os.getenv("PAYPAL_CLIENT_SECRET", "YOUR_PAYPAL_CLIENT_SECRET")
    PAYPAL_MODE: str = os.getenv("PAYPAL_MODE", "sandbox")

    USDA_API_KEY: str = os.getenv("USDA_API_KEY", "YOUR_USDA_FDC_API_KEY")
    MYFITNESSPAL_API_KEY: str = os.getenv("MYFITNESSPAL_API_KEY", "YOUR_MFP_API_KEY_HYPOTHETICAL")

    POSE_ESTIMATION_MODEL_PATH: str = os.getenv("POSE_ESTIMATION_MODEL_PATH", "backend/models/mmovenet-tflite-singlepose-thunder.tflite")

    BACKEND_CORS_ORIGINS: str = os.getenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost,http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080,http://localhost:63342,null"
    )  # Added http://localhost:63342


    FIREBASE_SERVICE_ACCOUNT_KEY_PATH: Optional[str] = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", "backend/firebase-service-account-key.json")

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"),
        env_file_encoding='utf-8',
        extra='ignore'
    )


settings = Settings()

# Print effective paths for debugging startup
print(
    f"INFO: Config loaded. Project root for .env (expected): {os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}")
print(f"INFO: Effective DATABASE_URL from settings: {settings.DATABASE_URL}")
print(f"INFO: Effective POSE_ESTIMATION_MODEL_PATH from settings: {settings.POSE_ESTIMATION_MODEL_PATH}")
print(f"INFO: Effective BACKEND_CORS_ORIGINS: {settings.BACKEND_CORS_ORIGINS}")

env_file_path_check = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
if not os.path.exists(env_file_path_check):
    print(
        f"WARNING: .env file NOT FOUND at expected location: {env_file_path_check}. Using default settings or environment variables.")
else:
    print(f"INFO: .env file found and loaded from: {env_file_path_check}")