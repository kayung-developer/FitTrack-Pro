from fastapi import APIRouter, Depends, HTTPException, Request, Header, status, Query
from sqlalchemy.orm import Session
from typing import List, Any, Dict, Optional
import json # For webhook payload parsing

from backend import schemas as pydantic_schemas, models as db_models, crud
from backend.database import get_db
from backend.core.security import get_current_active_user
from backend.core.config import settings
from backend.services import payment_service

router = APIRouter()

# --- Stripe Payments ---
@router.post("/stripe/create-payment-intent", response_model=pydantic_schemas.PaymentIntentResponse)
async def create_stripe_payment(
    payment_intent_create: pydantic_schemas.PaymentIntentCreate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_active_user)
):
    try:
        intent = await payment_service.create_stripe_payment_intent(
            db=db,
            user_id=current_user.id,
            amount_usd=payment_intent_create.amount,
            currency=payment_intent_create.currency,
            description=f"Consultation: {payment_intent_create.consultation_type}",
            consultation_type=payment_intent_create.consultation_type
        )
        return pydantic_schemas.PaymentIntentResponse(
            client_secret=intent.client_secret,
            payment_intent_id=intent.id,
            publishable_key=settings.STRIPE_PUBLISHABLE_KEY # Send publishable key to frontend
        )
    except HTTPException as e: # Re-raise HTTPExceptions from service
        raise e
    except Exception as e:
        print(f"Error in create_stripe_payment endpoint: {e}") # Log for server admin
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create Stripe payment intent.")


@router.post("/stripe/webhook", include_in_schema=False) # Exclude from OpenAPI docs for security
async def stripe_webhook_handler( # Renamed for clarity
    request: Request,
    stripe_signature: Optional[str] = Header(None), # Stripe sends 'Stripe-Signature'
    db: Session = Depends(get_db)
):
    if stripe_signature is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature header")

    try:
        payload_bytes = await request.body()
        payload_dict = json.loads(payload_bytes.decode("utf-8")) # Parse JSON from bytes
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload in webhook")
    except Exception as e: # Catch other potential errors during body reading/parsing
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error reading webhook payload: {e}")

    try:
        result = await payment_service.handle_stripe_webhook(
            payload_dict=payload_dict,
            sig_header=stripe_signature,
            db=db
        )
        return result
    except HTTPException as e: # Re-raise HTTPExceptions from service
        raise e
    except Exception as e:
        print(f"CRITICAL Error in Stripe webhook processing: {e}") # Log for server admin
        # Avoid sending detailed internal errors back to Stripe if possible,
        # but for now, let FastAPI's default error handling take over or return a generic 500.
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook processing error on server.")


# --- PayPal Payments (Conceptual) ---
@router.post("/paypal/create-order", response_model=pydantic_schemas.PaypalOrderResponse)
async def create_paypal_payment_order(
    order_create: pydantic_schemas.PaypalOrderCreate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_active_user)
):
    # This would integrate with PayPal SDK
    print(f"Conceptual: User {current_user.id} attempting PayPal order: {order_create.dict()}")
    # In a real scenario, you'd store order details in your DB (pending)
    # and link user_id, consultation_type.
    try:
        response = await payment_service.create_paypal_order(db=db, user_id=current_user.id, order_create_schema=order_create)
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error creating PayPal order (conceptual): {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create PayPal order (conceptual).")


@router.post("/paypal/capture-order/{order_id}", response_model=Dict[str, Any]) # Response type might be more specific
async def capture_paypal_payment_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_active_user)
):
    # After user approves on PayPal, frontend calls this to finalize
    # This would integrate with PayPal SDK to capture the payment
    # Update DB with payment status, transaction ID.
    print(f"Conceptual: User {current_user.id} attempting to capture PayPal order: {order_id}")
    try:
        response = await payment_service.capture_paypal_order(db=db, order_id=order_id, user_id=current_user.id)
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error capturing PayPal order (conceptual): {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to capture PayPal order (conceptual).")


# --- Crypto Payments (Conceptual) ---
@router.post("/crypto/request-payment", response_model=pydantic_schemas.CryptoPaymentResponse)
async def request_crypto_payment(
    crypto_request: pydantic_schemas.CryptoPaymentRequest,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_active_user)
):
    print(f"Conceptual: User {current_user.id} requesting crypto payment: {crypto_request.dict()}")
    try:
        response = await payment_service.create_crypto_payment_request(db=db, user_id=current_user.id, crypto_request_schema=crypto_request)
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error requesting crypto payment (conceptual): {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to request crypto payment (conceptual).")


@router.get("/crypto/status/{payment_request_id}", response_model=Dict[str, Any])
async def check_crypto_payment_status_endpoint( # Renamed for clarity
    payment_request_id: str,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_active_user)
):
    # Polls the crypto payment processor for status or handles webhook callback
    # Update DB on confirmation.
    print(f"Conceptual: User {current_user.id} checking crypto payment status for: {payment_request_id}")
    try:
        response = await payment_service.check_crypto_payment_status(db=db, payment_request_id=payment_request_id, user_id=current_user.id)
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error checking crypto payment status (conceptual): {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to check crypto payment status (conceptual).")


# --- Payment History for Current User ---
@router.get("/history", response_model=List[pydantic_schemas.PaymentRecordSchema])
def get_user_payment_history(
    skip: int = 0,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_active_user)
):
    records = crud.payment_record.get_multi_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return records