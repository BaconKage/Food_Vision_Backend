import datetime

from app.schemas import AIFoodItem
from app.services.mealplan_service import deduplicate_ai_foods, utc_day_start


def test_deduplicate_ai_foods_keeps_best_confidence_and_macros():
    items = [
        AIFoodItem(
            name="Paneer",
            serving=1,
            weight_g=100,
            calories=250,
            protein_g=15,
            carbs_g=5,
            fats_g=18,
            confidence=0.61,
        ),
        AIFoodItem(
            name="paneer",
            serving=1,
            weight_g=120,
            calories=280,
            protein_g=20,
            carbs_g=8,
            fats_g=21,
            confidence=0.73,
        ),
    ]

    dedup = deduplicate_ai_foods(items)

    assert len(dedup) == 1
    assert dedup[0].name.lower() == "paneer"
    assert dedup[0].confidence == 0.73
    assert dedup[0].calories == 280


def test_utc_day_start_normalization():
    dt = datetime.datetime(2026, 3, 4, 22, 30, tzinfo=datetime.UTC)
    normalized = utc_day_start(dt)
    assert normalized == datetime.datetime(2026, 3, 4, 0, 0, tzinfo=datetime.UTC)
