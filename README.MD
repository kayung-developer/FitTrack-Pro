# FitTrack Pro - Advanced Fitness Tracking Dashboard

## Overview

This project is a comprehensive, fully functional FitTrack Pro - Advanced Fitness Tracking Dashboard. It features a rich frontend built with HTML, CSS, JavaScript (React via CDN), and a powerful backend powered by Python (FastAPI). The application aims to provide a seamless and intelligent experience for users to track their fitness journey, manage workouts, log nutrition, monitor sleep, and much more, including advanced features like AI-driven insights and payment system integration for consultations.

The CV Service for exercise form analysis uses a TFLite model (e.g., MoveNet) for pose estimation.

## Core Features (Implemented / Partially Implemented)

*   **User Profile & Health Metrics:** Personalized profiles, BMI, BMR, TDEE calculations.
*   **Real-Time Activity Tracking (Manual Logging):** Log steps, distance, calories, heart rate, GPS-based activities, workout types.
*   **Workout & Training Management:** Custom workout planner, exercise library.
    *   *AI Recommendations (Conceptual)*
    *   *Exercise Form Tracking via CV (Functional with MoveNet TFLite model)*
*   **Diet & Nutrition Logging:** Macro/micronutrient tracking (manual), barcode scanner integration (via Open Food Facts), food database integration (USDA).
*   **Sleep & Recovery Monitoring (Manual Logging):** Sleep duration, cycle analysis (manual input).
*   **Progress Analytics & Visualizations:** Basic trend charts (weight, calories - example).
*   **Integrations & Syncing (Conceptual for UI):** UI placeholders for syncing with wearables and other apps.
*   **Payment System Integration:** Stripe for consultation bookings (functional with test keys), conceptual placeholders for PayPal & Crypto.

## Future Advancements (Conceptual / UI Placeholders)

*   AI & Predictive Health Modeling
*   3D & AR/VR Integration
*   IoT & Smart Gym Equipment Sync
*   Mental Wellness & Biofeedback
*   Telehealth & Trainer Live Support
*   Genetic & Epigenetic Fitness Insights
*   Blockchain for Fitness Data Security
*   Sustainability & Eco-Friendly Metrics

## Tech Stack

*   **Backend:** Python 3.9+, FastAPI, SQLAlchemy, Pydantic, Uvicorn
*   **Database:** SQLite (default), easily configurable for PostgreSQL etc.
*   **Frontend:** HTML5, CSS3, JavaScript (ES6+), React 18 (via CDN), Chart.js (via CDN)
*   **Authentication:** JWT (JSON Web Tokens)
*   **Payments:** Stripe (primary integration)
*   **APIs:** Open Food Facts (for barcode scanning), USDA FoodData Central (for food lookup)
*   **CV (Pose Estimation):** TensorFlow Lite Runtime, OpenCV, NumPy with MoveNet model.

## Project Structure

```
advanced-fitness-dashboard/
├── backend/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py       # Application settings, API keys
│   │   └── security.py     # Password hashing, JWT creation
│   ├── crud.py             # Database Create, Read, Update, Delete operations
│   ├── database.py         # Database engine and session setup
│   ├── main.py             # FastAPI application entry point
│   ├── models.py           # SQLAlchemy ORM models
│   ├── routers/            # API endpoint definitions
│   │   ├── __init__.py
│   │   ├── activities.py
│   │   ├── advanced.py
│   │   ├── auth.py
│   │   ├── nutrition.py
│   │   ├── payments.py
│   │   ├── sleep.py
│   │   ├── users.py
│   │   └── workouts.py
│   ├── schemas.py          # Pydantic schemas for data validation and serialization
│   └── services/           # Business logic, external API integrations
│       ├── __init__.py
│       ├── activity_service.py
│       ├── blockchain_service.py (Conceptual)
│       ├── cv_service.py (Conceptual, with model loading placeholder)
│       ├── iot_service.py (Conceptual)
│       ├── nutrition_service.py
│       ├── payment_service.py
│       ├── user_service.py
│       └── workout_service.py
├── frontend.html           # Single HTML file for the frontend (React via CDN)
├── requirements.txt        # Python backend dependencies
├── .env.example            # Example environment variables file
└── README.md               # This file
```


## Prerequisites

*   Python 3.9 or higher
*   `pip` (Python package installer)
*   A modern web browser
*   **Pose Estimation Model:** A `.tflite` pose estimation model (e.g., MoveNet SinglePose Lightning).
*   Stripe Account (for testing payments - use test keys)
*   USDA API Key (for food database lookup)

## Setup Instructions

1.  **Clone the Repository (or create the structure manually):**
    If you have the code, place `frontend.html`, `README.md` in the root. Create the `backend/` directory and populate it with the Python files. Create `backend/models/` directory for the TFLite model.

2.  **AI/ML/CV Model Setup (Pose Estimation)**
    *   **Model Choice:** This project is configured to use a TensorFlow Lite (TFLite) pose estimation model. **MoveNet (SinglePose Lightning or Thunder)** is highly recommended.
        *   **MoveNet Lightning:** Faster, good for real-time applications on less powerful devices, slightly less accurate.
        *   **MoveNet Thunder:** More accurate, slightly slower, better for applications where precision is key.
    *   **Download Model:**
        1.  Go to [TensorFlow Hub](https://tfhub.dev/).
        2.  Search for "MoveNet SinglePose Lightning TFLite" or "MoveNet SinglePose Thunder TFLite".
        3.  Download the `.tflite` model file. For instance, from a URL like `https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/float16/4` (this is an example, always check TF Hub for the latest versions and models).
    *   **Placement:**
        1.  Create a directory `backend/models/` if it doesn't exist.
        2.  Place the downloaded `.tflite` file into this directory. For example, rename it to `movenet_lightning.tflite`.
    *   **Configuration:**
        1.  Open your `.env` file (create from `.env.example` if you haven't).
        2.  Set the `POSE_ESTIMATION_MODEL_PATH` variable to the correct path relative to where the backend application runs (usually the project root).
            Example if `uvicorn` is run from the project root:
            ```env
            POSE_ESTIMATION_MODEL_PATH="backend/models/movenet_lightning.tflite"
            ```
            If `uvicorn` is run from the `backend` directory:
            ```env
            POSE_ESTIMATION_MODEL_PATH="models/movenet_lightning.tflite"
            ```
    *   **Dependencies:** Ensure CV-related Python libraries are installed (see `requirements.txt`):
        `opencv-python`, `tensorflow-lite-runtime` (or `tensorflow`), `numpy`.

3.  **Backend Setup:**
    *   Navigate to the project root: `cd advanced-fitness-dashboard/`
    *   Create and activate a Python virtual environment:
        ```bash
        python -m venv venv
        # On Windows: .\venv\Scripts\activate
        # On macOS/Linux: source venv/bin/activate
        ```
    *   Install Python dependencies:
        ```bash
        pip install -r requirements.txt
        ```
    *   Create and configure the environment file `.env` from `.env.example` in the project root. Update API keys, `SECRET_KEY`, `DATABASE_URL`, and `POSE_ESTIMATION_MODEL_PATH`.

4.  **Frontend Setup:**
    *   Open `frontend.html`.
    *   Update `API_BASE_URL` if your backend runs on a different port/address.
    *   Update `STRIPE_PUBLISHABLE_KEY` with your Stripe publishable test key.

5.  **Database Initialization:**
    The first time the FastAPI backend starts, SQLAlchemy will create the `fitness_tracker.db` (SQLite) file in the `backend/` directory (or as configured in `DATABASE_URL`) and all tables.

## Running the Application

1.  **Start the Backend Server:**
    *   From the project root directory (`advanced-fitness-dashboard/`), with your virtual environment activated:
        ```bash
        uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
        ```
    *   The backend API will be at `http://localhost:8000`. The CV service will attempt to load the model specified by `POSE_ESTIMATION_MODEL_PATH`. Check console output for model loading status.

2.  **Access the Frontend Application:**
    *   Open `frontend.html` in your web browser (e.g., by double-clicking or using a simple HTTP server for serving static files if needed).

3.  **API Documentation (Swagger UI):**
    *   `http://localhost:8000/api/v1/docs`

4.  **Stripe Webhook (for payment confirmation):**
    *   Use Stripe CLI: `stripe listen --forward-to localhost:8000/api/v1/payments/stripe/webhook`
    *   Update `STRIPE_WEBHOOK_SECRET` in `.env` with the secret provided by the CLI.

## Key Environment Variables (.env)

*   `DATABASE_URL`: e.g., `sqlite:///./backend/fitness_tracker.db`
*   `SECRET_KEY`: Strong random string for JWT.
*   `POSE_ESTIMATION_MODEL_PATH`: Path to your TFLite model, e.g., `backend/models/movenet_lightning.tflite`.
*   `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`.
*   `USDA_API_KEY`.
*   `BACKEND_CORS_ORIGINS`: Comma-separated list of allowed frontend origins.

## Important Notes & Limitations

*   **Frontend:** Single HTML file with CDN React. For production, a separate React project with a build process is recommended.
*   **CV Service:** The `cv_service.py` is functional for pose estimation with a correctly configured MoveNet model. Analysis logic for specific exercises (squats, push-ups) is implemented; more exercises can be added.
*   **Conceptual Features:** Many "Future Advancements" remain conceptual.
*   **Security:** Production deployment requires further security hardening.
---

This README provides a comprehensive guide to setting up and running the Advanced Fitness Tracking Dashboard.
```

```
# backend/requirements.txt
fastapi
uvicorn[standard]
sqlalchemy
pydantic-settings
pydantic[email] # For EmailStr validation
python-dotenv
passlib[bcrypt] # For password hashing
python-jose[cryptography] # For JWT
httpx # For asynchronous HTTP requests to external APIs
stripe # Stripe Python library
python-multipart # For FastAPI file uploads / form data
# email-validator # Often a dependency for Pydantic's EmailStr, good to list explicitly
# opencv-python # If CV service was fully implemented for image processing
# tensorflow-lite # Or tflite-runtime, if CV service was fully implemented
```

```ini
# .env.example
# Copy this file to .env and fill in your actual values.
# Do NOT commit your .env file with real secrets to version control.

# Database Configuration
DATABASE_URL="sqlite:///./fitness_tracker.db"
# Example for PostgreSQL:
# DATABASE_URL="postgresql://user:password@localhost:5432/fitness_db"

# JWT Authentication
SECRET_KEY="YOUR_VERY_STRONG_AND_SECRET_RANDOM_KEY_HERE_MIN_32_CHARS" # Change this! Generate with: openssl rand -hex 32
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=10080 # 7 days

# Payment Gateway API Keys
STRIPE_SECRET_KEY="sk_test_YOUR_STRIPE_SECRET_KEY"
STRIPE_PUBLISHABLE_KEY="pk_test_YOUR_STRIPE_PUBLISHABLE_KEY"
STRIPE_WEBHOOK_SECRET="whsec_YOUR_STRIPE_WEBHOOK_SECRET_FROM_CLI_LISTEN" # Get from `stripe listen`

# For conceptual PayPal integration (if implemented)
PAYPAL_CLIENT_ID="YOUR_PAYPAL_CLIENT_ID"
PAYPAL_CLIENT_SECRET="YOUR_PAYPAL_CLIENT_SECRET"
# PAYPAL_MODE="sandbox" # or "live"

# External API Keys
USDA_API_KEY="YOUR_USDA_FDC_API_KEY" # Get from https://fdc.nal.usda.gov/api-key-signup.html
MYFITNESSPAL_API_KEY="YOUR_MFP_API_KEY" # Hypothetical, MyFitnessPal does not have a public general food API

# Computer Vision Model Path (Example)
# Relative to the 'backend' directory if the app is run from project root, or an absolute path.
POSE_ESTIMATION_MODEL_PATH="models/posenet_mobilenet_v1_100_257x257_multi_kpt_stripped.tflite" # You need to obtain and place this model
