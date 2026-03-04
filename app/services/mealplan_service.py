from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Dict, List, Tuple

from bson import ObjectId
from pymongo.collection import Collection

from app.config import get_settings
from app.db import foods_collection, mealplans_collection, users_collection
from app.schemas import AIFoodItem, AddedItem


class BadRequestError(Exception):
    pass


class NotFoundError(Exception):
    pass


@dataclass
class PreparedFood:
    food_oid: ObjectId
    name: str
    serving: float
    weight_g: float
    calories: float
    protein_g: float
    carbs_g: float
    fats_g: float


def parse_object_id(value: str, field_name: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise BadRequestError(f"{field_name} must be a valid ObjectId")
    return ObjectId(value)


def utc_day_start(now: datetime | None = None) -> datetime:
    current = now.astimezone(UTC) if now else datetime.now(UTC)
    return datetime(current.year, current.month, current.day, tzinfo=UTC)


def ensure_user_exists(user_oid: ObjectId, field_name: str, users_col: Collection | None = None) -> None:
    users_col = users_col or users_collection()
    if users_col.count_documents({"_id": user_oid}, limit=1) == 0:
        raise NotFoundError(f"{field_name} does not exist")


def deduplicate_ai_foods(items: List[AIFoodItem]) -> List[AIFoodItem]:
    dedup: Dict[str, AIFoodItem] = {}
    for item in items:
        key = item.name.strip().lower()
        if key not in dedup:
            dedup[key] = item
            continue

        current = dedup[key]
        # Keep the highest-confidence variant, but preserve non-zero nutrition from either.
        winner = item if item.confidence >= current.confidence else current
        merged = AIFoodItem(
            name=winner.name,
            serving=winner.serving or current.serving or item.serving,
            weight_g=max(current.weight_g, item.weight_g),
            calories=max(current.calories, item.calories),
            protein_g=max(current.protein_g, item.protein_g),
            carbs_g=max(current.carbs_g, item.carbs_g),
            fats_g=max(current.fats_g, item.fats_g),
            confidence=max(current.confidence, item.confidence),
        )
        dedup[key] = merged

    return list(dedup.values())


def _format_number_str(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _find_or_create_food(item: AIFoodItem, now: datetime, foods_col: Collection) -> ObjectId:
    escaped = re.escape(item.name.strip())
    existing = foods_col.find_one({"name": {"$regex": f"^{escaped}$", "$options": "i"}}, {"_id": 1, "name": 1})
    if existing:
        return existing["_id"]

    food_doc = {
        "name": item.name.strip(),
        "nutrition": {
            "calories": float(item.calories),
            "protein_g": float(item.protein_g),
            "carbs_g": float(item.carbs_g),
            "fats_g": float(item.fats_g),
            "weight_g": float(item.weight_g),
        },
        "created_at": now,
        "updated_at": now,
    }
    result = foods_col.insert_one(food_doc)
    return result.inserted_id


def prepare_foods(items: List[AIFoodItem]) -> List[PreparedFood]:
    now = datetime.now(UTC)
    foods_col = foods_collection()
    output: List[PreparedFood] = []

    for item in items:
        food_oid = _find_or_create_food(item, now, foods_col)
        output.append(
            PreparedFood(
                food_oid=food_oid,
                name=item.name,
                serving=float(item.serving or 1),
                weight_g=float(item.weight_g or 0),
                calories=float(item.calories or 0),
                protein_g=float(item.protein_g or 0),
                carbs_g=float(item.carbs_g or 0),
                fats_g=float(item.fats_g or 0),
            )
        )
    return output


def _build_foods_list_entries(prepared_foods: List[PreparedFood]) -> Tuple[List[dict], List[AddedItem]]:
    foods_list = []
    added_items: List[AddedItem] = []

    for item in prepared_foods:
        details = {
            "_id": ObjectId(),
            "protein": _format_number_str(item.protein_g),
            "weight": _format_number_str(item.weight_g),
            "cals": _format_number_str(item.calories),
            "carbs": _format_number_str(item.carbs_g),
            "zinc": "",
            "iron": "",
            "magnesium": "",
            "sulphur": "",
            "fats": _format_number_str(item.fats_g),
            "others": "",
        }
        foods_entry = {
            "_id": ObjectId(),
            "food": item.food_oid,
            "serving": item.serving,
            "details": details,
            "completed": False,
        }
        foods_list.append(foods_entry)
        added_items.append(
            AddedItem(
                food_id=str(item.food_oid),
                food_name=item.name,
                serving=item.serving,
                cals=details["cals"],
                protein=details["protein"],
                carbs=details["carbs"],
                fats=details["fats"],
            )
        )

    return foods_list, added_items


def validate_confident_foods(items: List[AIFoodItem]) -> None:
    settings = get_settings()
    if not items:
        raise BadRequestError("No foods identified in image")

    high_confidence = [i for i in items if i.confidence >= settings.min_food_confidence]
    unknown_named = [i for i in items if i.name.strip().lower() in {"unknown", "uncertain", "unidentified food"}]

    if not high_confidence or unknown_named:
        raise BadRequestError("Food detection is too uncertain. Please upload a clearer image.")


def upsert_mealplan(
    created_for_oid: ObjectId,
    created_by_oid: ObjectId,
    meal_oid: ObjectId,
    prepared_foods: List[PreparedFood],
) -> Tuple[ObjectId, datetime, List[AddedItem]]:
    now = datetime.now(UTC)
    for_date = utc_day_start(now)

    mealplans_col = mealplans_collection()
    foods_list, added_items = _build_foods_list_entries(prepared_foods)

    existing = mealplans_col.find_one(
        {"created_for": created_for_oid, "for_date": for_date, "deleted_at": None},
        {"_id": 1},
    )

    if not existing:
        doc = {
            "for_date": for_date,
            "created_by": created_by_oid,
            "created_for": created_for_oid,
            "deleted_at": None,
            "created_at": now,
            "updated_at": now,
            "mealPlan": [{"_id": ObjectId(), "meals": meal_oid, "foodsList": foods_list}],
            "__v": 1,
        }
        result = mealplans_col.insert_one(doc)
        return result.inserted_id, for_date, added_items

    mealplan_id = existing["_id"]
    update_with_existing_meal = mealplans_col.update_one(
        {"_id": mealplan_id, "mealPlan.meals": meal_oid},
        {
            "$push": {"mealPlan.$.foodsList": {"$each": foods_list}},
            "$set": {"updated_at": now},
        },
    )

    if update_with_existing_meal.matched_count == 0:
        mealplans_col.update_one(
            {"_id": mealplan_id},
            {
                "$push": {"mealPlan": {"_id": ObjectId(), "meals": meal_oid, "foodsList": foods_list}},
                "$set": {"updated_at": now},
            },
        )

    return mealplan_id, for_date, added_items
