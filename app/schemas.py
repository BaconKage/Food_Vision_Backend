from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class AIFoodItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    serving: float = Field(default=1, ge=0)
    weight_g: float = Field(default=0, ge=0)
    calories: float = Field(default=0, ge=0)
    protein_g: float = Field(default=0, ge=0)
    carbs_g: float = Field(default=0, ge=0)
    fats_g: float = Field(default=0, ge=0)
    confidence: float = Field(default=0, ge=0, le=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class OpenAIVisionPayload(BaseModel):
    foods: List[AIFoodItem] = Field(default_factory=list)
    notes: Optional[str] = ""


class AddedItem(BaseModel):
    food_id: str
    food_name: str
    serving: float
    cals: str
    protein: str
    carbs: str
    fats: str


class UploadResponse(BaseModel):
    ok: bool
    mealplan_id: str
    for_date: str
    created_for_id: str
    created_by_id: str
    meal_id: str
    added_items: List[AddedItem]
