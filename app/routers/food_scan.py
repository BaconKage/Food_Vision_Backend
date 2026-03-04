from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.schemas import UploadResponse
from app.services.mealplan_service import (
    BadRequestError,
    NotFoundError,
    deduplicate_ai_foods,
    ensure_user_exists,
    parse_object_id,
    prepare_foods,
    upsert_mealplan,
    validate_confident_foods,
)
from app.services.openai_service import OpenAIVisionService, VisionServiceError

router = APIRouter(prefix="/api/food-scan", tags=["food-scan"])


@router.post("/upload", response_model=UploadResponse)
async def upload_food_scan(
    created_for_id: str = Form(...),
    created_by_id: str = Form(...),
    meal_id: str = Form(...),
    photo: UploadFile = File(...),
) -> UploadResponse:
    settings = get_settings()

    if not photo.content_type or photo.content_type.lower() not in {"image/jpeg", "image/jpg", "image/png"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="photo must be a jpg or png image")

    image_bytes = await photo.read()
    max_size_bytes = settings.max_image_mb * 1024 * 1024
    if len(image_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="photo is empty")
    if len(image_bytes) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"photo exceeds max size of {settings.max_image_mb}MB",
        )

    try:
        created_for_oid = parse_object_id(created_for_id, "created_for_id")
        created_by_oid = parse_object_id(created_by_id, "created_by_id")
        meal_oid = parse_object_id(meal_id, "meal_id")

        ensure_user_exists(created_for_oid, "created_for_id")
        ensure_user_exists(created_by_oid, "created_by_id")

        vision_service = OpenAIVisionService()
        model_payload = vision_service.scan_food_image(image_bytes=image_bytes, mime_type=photo.content_type)

        unique_foods = deduplicate_ai_foods(model_payload.foods)
        validate_confident_foods(unique_foods)

        prepared_foods = prepare_foods(unique_foods, created_by_oid)
        mealplan_id, for_date, added_items = upsert_mealplan(
            created_for_oid=created_for_oid,
            created_by_oid=created_by_oid,
            meal_oid=meal_oid,
            prepared_foods=prepared_foods,
        )

        return UploadResponse(
            ok=True,
            mealplan_id=str(mealplan_id),
            for_date=for_date.isoformat().replace("+00:00", "Z"),
            created_for_id=created_for_id,
            created_by_id=created_by_id,
            meal_id=meal_id,
            added_items=added_items,
        )

    except BadRequestError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except VisionServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Vision service error: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected server error: {exc}") from exc
