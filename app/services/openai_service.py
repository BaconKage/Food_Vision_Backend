import base64
import json
import logging
import time
from typing import Any, Dict

from openai import OpenAI
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import OpenAIVisionPayload

logger = logging.getLogger(__name__)


class VisionServiceError(Exception):
    pass


def _extract_text_payload(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text.strip()

    chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") == "output_text" and getattr(content, "text", ""):
                chunks.append(content.text)
    return "\n".join(chunks).strip()


class OpenAIVisionService:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key)

    def scan_food_image(self, image_bytes: bytes, mime_type: str) -> OpenAIVisionPayload:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "You are a nutrition vision model. Analyze the food image and return ONLY valid JSON with this exact shape: "
            '{"foods":[{"name":"string","serving":1,"weight_g":100,"calories":250,"protein_g":10,"carbs_g":30,'
            '"fats_g":8,"confidence":0.0}],"notes":"optional short"}. '
            "Rules: no markdown, no comments, no extra keys, no text outside JSON. "
            "If uncertain, set lower confidence and use best estimate. Names must be common singular food names."
        )

        last_error: Exception | None = None
        for attempt in range(1, self._settings.openai_max_retries + 1):
            try:
                response = self._client.responses.create(
                    model=self._settings.openai_model,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": prompt},
                                {
                                    "type": "input_image",
                                    "image_url": f"data:{mime_type};base64,{b64_image}",
                                },
                            ],
                        }
                    ],
                    temperature=0,
                )

                raw_text = _extract_text_payload(response)
                if not raw_text:
                    raise VisionServiceError("OpenAI returned empty response")

                parsed: Dict[str, Any] = json.loads(raw_text)
                return OpenAIVisionPayload.model_validate(parsed)
            except (json.JSONDecodeError, ValidationError, Exception) as exc:
                last_error = exc
                logger.warning("Vision request failed on attempt %s/%s: %s", attempt, self._settings.openai_max_retries, exc)
                if attempt < self._settings.openai_max_retries:
                    time.sleep(0.8 * attempt)

        raise VisionServiceError(f"Vision model failed after retries: {last_error}")
