import httpx
from backend.core.config import settings
from backend import schemas  # Use the alias for Pydantic schemas
from typing import Optional, Dict, Any, Union


async def fetch_food_data_from_usda(food_name: str) -> Union[schemas.USDAFoodItem, Dict[str, Any]]:
    """
    Fetches food data from USDA FoodData Central API.
    Requires an API key from: https://fdc.nal.usda.gov/api-key-signup.html
    """
    api_key = settings.USDA_API_KEY
    if not api_key or api_key == "YOUR_USDA_FDC_API_KEY":  # Check if placeholder key
        return {"error": "USDA API key not configured or is a placeholder."}

    base_url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {
        "query": food_name,
        "api_key": api_key,
        "pageSize": 1,  # Get the top result
        "dataType": "Branded,Foundation,SR Legacy"  # Search across multiple data types
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("foods") and len(data["foods"]) > 0:
                food_info_raw = data["foods"][0]
                # Parse into Pydantic schema for type safety and structure
                # This requires careful mapping of USDA fields to schemas.USDANutrient

                # Simplified parsing for direct return, full parsing should use Pydantic models
                # Example:
                # nutrients_parsed = []
                # for nutrient_raw in food_info_raw.get('foodNutrients', []):
                #     try:
                #         nutrients_parsed.append(schemas.USDANutrient.parse_obj(nutrient_raw))
                #     except Exception as e:
                #         print(f"Warning: Could not parse nutrient: {nutrient_raw.get('nutrientName')}, Error: {e}")

                # return schemas.USDAFoodItem(
                #     description=food_info_raw.get("description"),
                #     fdcId=food_info_raw.get("fdcId"),
                #     brandOwner=food_info_raw.get("brandOwner"),
                #     ingredients=food_info_raw.get("ingredients"),
                #     foodNutrients=nutrients_parsed
                # )
                return food_info_raw  # Return raw for now, frontend can parse or this service can be enhanced
            return {"message": f"Food item '{food_name}' not found in USDA database."}
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            try:  # Try to parse JSON error from USDA
                error_json = e.response.json()
                error_detail = error_json.get("message", error_json.get("error", {}).get("message", e.response.text))
            except:
                pass
            return {"error": f"USDA API request failed for '{food_name}': {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"error": f"USDA API request connection error for '{food_name}': {str(e)}"}
        except Exception as e:
            return {"error": f"An unexpected error occurred while fetching from USDA for '{food_name}': {str(e)}"}


async def fetch_food_data_from_barcode(barcode: str) -> Union[schemas.BarcodeLookupResponse, Dict[str, Any]]:
    """
    Fetches food data by barcode using Open Food Facts API.
    """
    if not barcode:
        return {"error": "Barcode not provided."}

    # Using v2 of Open Food Facts API
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    # Fields to request for smaller response, adjust as needed.
    # fields = "product_name,brands,nutriments,ingredients_text,image_front_url"
    # params = {"fields": fields}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url)  # , params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == 1 and data.get("product"):
                product_data = data["product"]
                # Parse into Pydantic model for structured response
                return schemas.BarcodeLookupResponse.parse_obj(data)
            elif data.get("status") == 0:  # Product not found
                return schemas.BarcodeLookupResponse(status=0, message=f"Product with barcode {barcode} not found.")
            return {"error": "Product not found or unknown API response structure.", "details": data}

        except httpx.HTTPStatusError as e:
            return {"error": f"Open Food Facts API request failed for barcode {barcode}: {e.response.status_code}",
                    "details": e.response.text}
        except httpx.RequestError as e:
            return {"error": f"Open Food Facts API request connection error for barcode {barcode}: {str(e)}"}
        except Exception as e:  # Includes JSONDecodeError if response is not JSON
            return {"error": f"An error occurred while fetching barcode data for {barcode}: {str(e)}"}


def map_external_food_data_to_log_schema(external_data: Any, source: str, barcode: Optional[str] = None) -> Optional[
    schemas.NutritionLogCreate]:
    """
    CONCEPTUAL: Maps data from an external source (USDA, OpenFoodFacts) to NutritionLogCreate schema.
    This requires detailed knowledge of each source's nutrient naming and structure.
    """
    if not external_data or isinstance(external_data, dict) and external_data.get("error"):
        return None

    log_data = schemas.NutritionLogCreate(food_item_name="Unknown Food Item")  # Default
    log_data.barcode = barcode

    if source == "usda" and isinstance(external_data, dict):
        log_data.food_item_name = external_data.get("description", "USDA Item")
        # Example mapping (needs specific nutrient IDs or names from USDA response)
        # for nutrient in external_data.get("foodNutrients", []):
        #     if nutrient.get("nutrientName") == "Energy" and nutrient.get("unitName") == "KCAL":
        #         log_data.calories = nutrient.get("value")
        #     elif nutrient.get("nutrientName") == "Protein":
        #         log_data.protein_g = nutrient.get("value")
        #     # ... and so on for carbs, fat, micronutrients
        print(f"Conceptual: Mapping USDA data for '{log_data.food_item_name}'")

    elif source == "openfoodfacts" and isinstance(external_data,
                                                  schemas.BarcodeLookupResponse) and external_data.product:
        product = external_data.product
        log_data.food_item_name = product.product_name or "OpenFoodFacts Item"
        if product.nutriments:
            log_data.calories = product.nutriments.energy_kcal_100g  # Note: this is per 100g, needs adjustment for serving size
            log_data.protein_g = product.nutriments.proteins_100g
            log_data.carbs_g = product.nutriments.carbohydrates_100g
            log_data.fat_g = product.nutriments.fat_100g
        # log_data.serving_size = product.serving_size (if available and parsed)
        print(f"Conceptual: Mapping OpenFoodFacts data for '{log_data.food_item_name}'")

    # This function needs significant expansion for accurate mapping and serving size handling.
    return log_data