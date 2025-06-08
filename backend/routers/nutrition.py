# backend/routers/nutrition.py
from fastapi import APIRouter, Depends, HTTPException, Query, status, Path
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime as dt_datetime  # Alias to avoid conflict with schema's datetime

from backend import crud, models, schemas as pydantic_schemas
from backend.database import get_db
from backend.core.security import get_current_active_user
from backend.services import nutrition_service

router = APIRouter()


@router.post("/", response_model=pydantic_schemas.NutritionLogSchema, status_code=status.HTTP_201_CREATED)
def log_nutrition_item_for_current_user(
        nutrition_log_in: pydantic_schemas.NutritionLogCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    return crud.nutrition_log.create_with_user(db=db, obj_in=nutrition_log_in, user_id=current_user.id)


@router.get("/", response_model=List[pydantic_schemas.NutritionLogSchema])
def read_nutrition_logs_for_current_user(
        skip: int = 0,
        limit: int = Query(default=20, ge=1, le=100),
        date_filter_str: Optional[str] = Query(None, alias="date", description="Filter by date YYYY-MM-DD"),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    date_obj = None
    if date_filter_str:
        try:
            date_obj = dt_datetime.strptime(date_filter_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use YYYY-MM-DD.")

    logs = crud.nutrition_log.get_multi_by_user(db, user_id=current_user.id, date_filter=date_obj, skip=skip,
                                                limit=limit)
    return logs


@router.get("/{log_id}", response_model=pydantic_schemas.NutritionLogSchema)
def read_single_nutrition_log_item(
        log_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_log = crud.nutrition_log.get(db, id=log_id)
    if not db_log or db_log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nutrition log not found or not authorized")
    return db_log


@router.put("/{log_id}", response_model=pydantic_schemas.NutritionLogSchema)
def update_user_nutrition_log_item(
        log_id: int,
        nutrition_log_in: pydantic_schemas.NutritionLogUpdate,  # Use Update schema
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_log = crud.nutrition_log.get(db, id=log_id)
    if not db_log or db_log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nutrition log not found or not authorized")
    return crud.nutrition_log.update(db, db_obj=db_log, obj_in=nutrition_log_in)


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_nutrition_log_item(
        log_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user)
):
    db_log = crud.nutrition_log.get(db, id=log_id)
    if not db_log or db_log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nutrition log not found or not authorized")
    crud.nutrition_log.remove(db, id=log_id)
    return


# --- External Food Database Integrations ---

@router.get("/food-database/search-usda", response_model=Any)
async def search_usda_food_database(
        query: str = Query(..., min_length=2, description="Food name to search"),
        # current_user: models.User = Depends(get_current_active_user) # Auth for rate limiting/user context
):
    result = await nutrition_service.fetch_food_data_from_usda(food_name=query)
    if isinstance(result, dict) and result.get("error"):
        if "API key not configured" in result["error"]:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result["error"])
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)
    if isinstance(result, dict) and result.get("message") and "not found" in result["message"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["message"])
    return result


@router.get("/food-database/lookup-barcode/{barcode}", response_model=Any)
async def lookup_food_by_barcode_openfoodfacts(
        barcode: str = Path(..., min_length=8, max_length=14, description="EAN/UPC barcode number"),
        # Changed Query to Path
        # current_user: models.User = Depends(get_current_active_user) # Uncomment if auth is needed
):
    result = await nutrition_service.fetch_food_data_from_barcode(barcode)
    if isinstance(result, dict) and result.get("error"):
        # If the service itself returns an error structure for 404s that aren't HTTP errors
        if "not found" in result.get("error", "").lower() or "not found" in result.get("message", "").lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=result.get("message", result.get("error")))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

    if isinstance(result, pydantic_schemas.BarcodeLookupResponse):  # If service returns Pydantic model
        if result.status == 0:  # Product not found by OpenFoodFacts
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=result.message or f"Product with barcode {barcode} not found.")
        if not result.product:  # Should not happen if status is 1, but good check
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                                detail="Barcode provider returned success status but no product data.")
    elif not result:  # If service returns None or empty for some reason other than error dict
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Failed to fetch or parse data from barcode provider (empty response).")

    return result