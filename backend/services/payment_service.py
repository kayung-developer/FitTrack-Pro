from typing import Optional, Dict, Any

import stripe
from sqlalchemy.orm import Session
from fastapi import HTTPException, status  # For raising HTTP errors

from backend.core.config import settings
from backend import models as db_models
from backend import schemas as pydantic_schemas
from backend import crud
from datetime import datetime

stripe.api_key = settings.STRIPE_SECRET_KEY


# --- Stripe ---
async def create_stripe_payment_intent(
        db: Session,
        user_id: int,
        amount_usd: float,
        currency: str = "usd",
        description: str = "Fitness Consultation Booking",
        consultation_type: Optional[str] = None  # Added for metadata
) -> stripe.PaymentIntent:
    if not settings.STRIPE_SECRET_KEY or "YOUR_STRIPE_SECRET_KEY" in settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe secret key not configured on server.")
    try:
        amount_cents = int(round(amount_usd * 100))  # Ensure it's integer cents
        if amount_cents <= 0:
            raise HTTPException(status_code=400, detail="Payment amount must be positive.")

        intent_params = {
            "amount": amount_cents,
            "currency": currency.lower(),
            "description": description,
            "payment_method_types": ['card'],
            "metadata": {
                'user_id': str(user_id),
                'service_description': description
            }
        }
        if consultation_type:
            intent_params["metadata"]['consultation_type'] = consultation_type

        intent = stripe.PaymentIntent.create(**intent_params)

        # Log this payment intent attempt in our database
        crud.payment_record.create_payment(
            db=db,
            user_id=user_id,
            amount=amount_usd,
            currency=currency,
            gateway=db_models.PaymentGatewayDB.STRIPE,
            transaction_id=None,  # Will be filled on webhook confirmation or PI ID if charge is direct
            status=db_models.PaymentStatusDB.PENDING,
            payment_intent_id=intent.id,
            # consultation_booking_id=... # Link if a booking record is created first
        )
        return intent
    except stripe.error.StripeError as e:
        print(f"Stripe API error: {e}")
        raise HTTPException(status_code=e.http_status or 500, detail=f"Stripe error: {e.user_message or str(e)}")
    except Exception as e:
        print(f"Error creating payment intent: {e}")
        raise HTTPException(status_code=500, detail="Could not create payment intent.")


async def handle_stripe_webhook(payload_dict: dict, sig_header: str, db: Session):
    if not settings.STRIPE_WEBHOOK_SECRET or "YOUR_STRIPE_WEBHOOK_SECRET" in settings.STRIPE_WEBHOOK_SECRET:
        print("CRITICAL: Stripe webhook secret not configured on server.")
        raise HTTPException(status_code=500, detail="Webhook secret not configured.")

    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload=payload_dict, sig_header=sig_header, secret=settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:  # Invalid payload
        print(f"Webhook ValueError (invalid payload): {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        print(f"Webhook SignatureVerificationError: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    # Handle the event
    if event.type == 'payment_intent.succeeded':
        payment_intent = event.data.object  # contains a stripe.PaymentIntent
        print(f"Webhook received: PaymentIntent {payment_intent.id} succeeded.")

        db_payment_record = crud.payment_record.get_by_payment_intent_id(db, payment_intent_id=payment_intent.id)
        if db_payment_record:
            # PaymentIntent object has `latest_charge` if a charge was created
            charge_id = payment_intent.latest_charge if payment_intent.latest_charge else payment_intent.id
            crud.payment_record.update_status(db, db_obj=db_payment_record, status=db_models.PaymentStatusDB.COMPLETED,
                                              transaction_id=charge_id)
            # TODO: Trigger post-payment actions (e.g., send confirmation email, unlock features/booking)
            print(f"Payment record {db_payment_record.id} updated to COMPLETED for PI {payment_intent.id}")
        else:
            print(
                f"Warning: Received Stripe success for unknown payment_intent_id: {payment_intent.id}. User ID from metadata: {payment_intent.metadata.get('user_id')}")
            # Potentially create a payment record here if it's missing but metadata is valid.

    elif event.type == 'payment_intent.payment_failed':
        payment_intent = event.data.object
        failure_reason = payment_intent.last_payment_error.message if payment_intent.last_payment_error else 'Unknown reason'
        print(f"Webhook received: PaymentIntent {payment_intent.id} failed. Reason: {failure_reason}")
        db_payment_record = crud.payment_record.get_by_payment_intent_id(db, payment_intent_id=payment_intent.id)
        if db_payment_record:
            crud.payment_record.update_status(db, db_obj=db_payment_record, status=db_models.PaymentStatusDB.FAILED)
            print(f"Payment record {db_payment_record.id} updated to FAILED for PI {payment_intent.id}")

    elif event.type == 'charge.refunded':
        charge = event.data.object
        # If you store charge_id as transaction_id
        db_payment_record = crud.payment_record.get_by_transaction_id(db, transaction_id=charge.id)
        if not db_payment_record and charge.payment_intent:  # Try finding by payment_intent_id if transaction_id was PI_id
            db_payment_record = crud.payment_record.get_by_payment_intent_id(db,
                                                                             payment_intent_id=charge.payment_intent)

        if db_payment_record:
            # Check if fully refunded
            if charge.refunded and charge.amount_refunded == charge.amount:
                crud.payment_record.update_status(db, db_obj=db_payment_record,
                                                  status=db_models.PaymentStatusDB.REFUNDED)
                print(f"Payment record {db_payment_record.id} (Charge {charge.id}) updated to REFUNDED.")
            # Partial refunds could be handled with a different status or notes.
        else:
            print(
                f"Warning: Received Stripe charge.refunded for unknown charge_id: {charge.id} or payment_intent: {charge.payment_intent}")


    # ... handle other event types as needed e.g. 'payment_intent.processing', 'payment_intent.canceled'
    else:
        print(f'Webhook received: Unhandled event type {event.type}')

    return {"status": "success", "event_type_received": event.type}


# --- PayPal (Conceptual) ---
async def create_paypal_order(
        db: Session,
        user_id: int,
        order_create_schema: pydantic_schemas.PaypalOrderCreate
) -> pydantic_schemas.PaypalOrderResponse:
    """CONCEPTUAL: Create a PayPal order. Requires PayPal SDK integration."""
    print(
        f"Conceptual: Creating PayPal order for user {user_id}, amount: {order_create_schema.amount} {order_create_schema.currency}")

    # 1. Integrate PayPal SDK (e.g., paypalrestsdk or direct HTTPS calls)
    # 2. Configure with settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET, settings.PAYPAL_MODE
    # 3. Create an order with purchase units, amount, currency, return_url, cancel_url.
    #    Example:
    #    order = paypalrestsdk.Order({
    #        "intent": "CAPTURE",
    #        "purchase_units": [{"amount": {"currency_code": currency, "value": str(amount)}}],
    #        "application_context": {"return_url": "...", "cancel_url": "..."}
    #    })
    #    if order.create():
    #        # Log pending payment in DB
    #        # Find approval_url in order.links
    #    else:
    #        raise HTTPException(...)

    # Mock response:
    mock_order_id = f"PAYPAL_ORDER_{datetime.utcnow().timestamp()}"
    mock_approve_url = f"https://www.sandbox.paypal.com/checkoutnow?token=FAKE_TOKEN_{mock_order_id}"

    crud.payment_record.create_payment(
        db=db, user_id=user_id, amount=order_create_schema.amount, currency=order_create_schema.currency,
        gateway=db_models.PaymentGatewayDB.PAYPAL, status=db_models.PaymentStatusDB.PENDING,
        transaction_id=mock_order_id  # Store PayPal order ID as transaction_id for now
    )
    return pydantic_schemas.PaypalOrderResponse(order_id=mock_order_id, approve_url=mock_approve_url)


async def capture_paypal_order(db: Session, order_id: str, user_id: int) -> Dict[str, Any]:
    """CONCEPTUAL: Capture payment for an approved PayPal order."""
    print(f"Conceptual: Capturing PayPal order {order_id} for user {user_id}")

    # 1. Use PayPal SDK to capture the order by order_id.
    #    order = paypalrestsdk.Order.find(order_id)
    #    if order.capture():
    #        # Update payment record in DB to 'completed', store final transaction ID from capture response
    #    else:
    #        # Update payment record to 'failed'

    db_payment_record = crud.payment_record.get_by_transaction_id(db,
                                                                  transaction_id=order_id)  # Assuming order_id stored as transaction_id
    if db_payment_record and db_payment_record.user_id == user_id:
        # Simulate capture
        final_paypal_tx_id = f"PAYPAL_CAPTURE_{order_id}"
        crud.payment_record.update_status(db, db_obj=db_payment_record, status=db_models.PaymentStatusDB.COMPLETED,
                                          transaction_id=final_paypal_tx_id)
        return {"status": "COMPLETED", "transaction_id": final_paypal_tx_id,
                "message": "PayPal payment captured (conceptual)."}
    elif db_payment_record:
        return {"status": "FAILED", "message": "User mismatch for PayPal order capture (conceptual)."}
    else:
        return {"status": "FAILED", "message": "PayPal order not found for capture (conceptual)."}


# --- Crypto Payments (Conceptual) ---
async def create_crypto_payment_request(
        db: Session,
        user_id: int,
        crypto_request_schema: pydantic_schemas.CryptoPaymentRequest
) -> pydantic_schemas.CryptoPaymentResponse:
    """CONCEPTUAL: Request a crypto payment. Requires integration with a crypto payment gateway."""
    print(
        f"Conceptual: Creating crypto payment request for user {user_id}, {crypto_request_schema.amount_crypto} {crypto_request_schema.crypto_currency}")

    # 1. Integrate with a crypto payment processor (e.g., BitPay, Coinbase Commerce, NowPayments).
    # 2. Generate a payment address and amount for the user.
    # 3. Provide a way to check payment status (webhook or polling).

    mock_payment_id = f"CRYPTO_PAYMENT_{datetime.utcnow().timestamp()}"
    mock_payment_address = f"FAKE_{crypto_request_schema.crypto_currency.upper()}_ADDRESS_{mock_payment_id}"
    mock_qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={mock_payment_address}"
    mock_status_check_url = f"{settings.API_V1_PREFIX}/payments/crypto/status/{mock_payment_id}"  # Our own endpoint to poll

    # Log pending payment in DB
    # Amount stored in DB might be USD equivalent at time of request, or the crypto amount.
    # For simplicity, let's assume amount_crypto is what we care about for now.
    crud.payment_record.create_payment(
        db=db, user_id=user_id,
        amount=crypto_request_schema.amount_crypto,  # Storing crypto amount
        currency=crypto_request_schema.crypto_currency,  # Storing crypto symbol as currency
        gateway=db_models.PaymentGatewayDB.CRYPTO, status=db_models.PaymentStatusDB.PENDING,
        transaction_id=mock_payment_id  # Using our internal payment ID for crypto tx
    )
    return pydantic_schemas.CryptoPaymentResponse(
        payment_address=mock_payment_address,
        qr_code_url=mock_qr_url,
        status_check_url=mock_status_check_url
    )


async def check_crypto_payment_status(db: Session, payment_request_id: str, user_id: int) -> Dict[str, Any]:
    """CONCEPTUAL: Check status of a crypto payment request."""
    print(f"Conceptual: Checking crypto payment status for {payment_request_id}, user {user_id}")

    # 1. Query the crypto payment processor API for the status of `payment_request_id`.
    # 2. If confirmed, update DB record.

    db_payment_record = crud.payment_record.get_by_transaction_id(db, transaction_id=payment_request_id)
    if db_payment_record and db_payment_record.user_id == user_id:
        if db_payment_record.status == db_models.PaymentStatusDB.COMPLETED:
            return {"payment_request_id": payment_request_id, "status": "CONFIRMED",
                    "message": "Crypto payment already confirmed."}

        # Simulate a check: randomly confirm after some time or based on a mock state
        import random
        if random.random() < 0.3:  # 30% chance of being "confirmed" for demo
            on_chain_tx_id = f"0x_FAKE_CRYPTO_TX_HASH_{payment_request_id}"
            # For crypto, the transaction_id in DB was our internal ID.
            # We might want to update it with the actual on-chain transaction hash, or add a new field.
            # For now, let's assume we update the existing transaction_id or add it to notes.
            db_payment_record.notes = f"On-chain TX: {on_chain_tx_id}"  # Example
            crud.payment_record.update_status(db, db_obj=db_payment_record, status=db_models.PaymentStatusDB.COMPLETED)
            return {"payment_request_id": payment_request_id, "status": "CONFIRMED", "on_chain_tx_id": on_chain_tx_id}
        else:
            return {"payment_request_id": payment_request_id, "status": "PENDING",
                    "message": "Awaiting crypto payment confirmation (conceptual)."}
    elif db_payment_record:
        return {"payment_request_id": payment_request_id, "status": "ERROR",
                "message": "User mismatch for crypto payment status check."}
    else:
        return {"payment_request_id": payment_request_id, "status": "NOT_FOUND",
                "message": "Crypto payment request not found."}