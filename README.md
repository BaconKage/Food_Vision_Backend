# Full Food Vision Backend

Production-ready FastAPI backend for uploading a food image, extracting foods/macros using OpenAI vision, ensuring foods exist in MongoDB, and inserting/updating a nested `mealplans` document.

## Features

- `POST /api/food-scan/upload` (multipart form-data)
- Validates `created_for_id` and `created_by_id` against `users` collection
- Uses OpenAI vision model (`OPENAI_MODEL`) with strict JSON prompt
- Parses + validates model output using Pydantic
- Deduplicates repeated foods in one request
- Ensures each detected food exists in `foods` collection (case-insensitive exact-name match)
- Upserts `mealplans` with required nested schema
- Sets `for_date` to current UTC day start (`00:00:00Z`)
- Structured error responses and logging

## Project Structure

```text
app/
  __init__.py
  main.py
  config.py
  db.py
  schemas.py
  routers/
    __init__.py
    food_scan.py
  services/
    __init__.py
    openai_service.py
    mealplan_service.py
tests/
  test_mealplan_service.py
requirements.txt
.env.example
Dockerfile
README.md
```

## Environment Variables

Copy `.env.example` to `.env` and fill values:

- `MONGODB_URI`
- `MONGODB_DB_NAME`
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default: `gpt-4.1-mini`)
- `MAX_IMAGE_MB` (optional, default: 8)
- `LOG_LEVEL` (optional, default: INFO)

## Setup (Local)

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
```

Run:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## API Usage

### Endpoint

`POST /api/food-scan/upload`

### Multipart Fields

- `created_for_id` (ObjectId string)
- `created_by_id` (ObjectId string)
- `meal_id` (ObjectId string)
- `photo` (`jpg`/`jpeg`/`png` file)

### curl Example

```bash
curl -X POST "http://localhost:8000/api/food-scan/upload" \
  -F "created_for_id=6728acaf65daa4872de45580" \
  -F "created_by_id=66fa4d6ad0d28b2e3eac932c" \
  -F "meal_id=6792218b6ebd09dd283eaf7f" \
  -F "photo=@/absolute/path/to/meal.jpg"
```

### Success Response Example

```json
{
  "ok": true,
  "mealplan_id": "67d1234ec9b0f7f87f108abc",
  "for_date": "2026-03-04T00:00:00Z",
  "created_for_id": "6728acaf65daa4872de45580",
  "created_by_id": "66fa4d6ad0d28b2e3eac932c",
  "meal_id": "6792218b6ebd09dd283eaf7f",
  "added_items": [
    {
      "food_id": "67c141939e82d4a119b92966",
      "food_name": "Paneer",
      "serving": 1,
      "cals": "280",
      "protein": "20",
      "carbs": "8",
      "fats": "21"
    }
  ]
}
```

### Error Cases

- `400`: invalid image type, empty file
- `404`: `created_for_id` or `created_by_id` not found in `users`
- `413`: file too large
- `422`: invalid ObjectId, uncertain/unknown AI result, no foods detected
- `502`: OpenAI model failed after retries
- `500`: DB/server error

## MongoDB Behavior

### `foods`

For each AI-detected food:

1. Case-insensitive exact-name lookup by `name`
2. If missing, insert:
   - `name`
   - `nutrition` with numeric defaults from AI (`calories`, `protein_g`, `carbs_g`, `fats_g`, `weight_g`)
   - `created_at`, `updated_at`

### `mealplans`

Upsert key:

- `created_for`
- `for_date` (UTC midnight)
- `deleted_at: null`

Behavior:

1. If no document exists: insert a new mealplan with one `mealPlan` item for `meal_id`
2. If exists:
   - update `updated_at`
   - if `mealPlan.meals == meal_id` exists, push new `foodsList` items into that meal entry
   - else push a new meal entry under `mealPlan`

`foodsList.details` fields are stored as strings for `protein`, `weight`, `cals`, `carbs`, `fats` to match existing schema.

## Run Tests

```bash
pytest -q
```

## Docker

Build:

```bash
docker build -t full-food-vision-backend .
```

Run:

```bash
docker run --rm -p 8000:8000 --env-file .env full-food-vision-backend
```

## Notes

- JWT/auth is intentionally not implemented yet.
- `created_for_id` and `created_by_id` are trusted from frontend but still validated against `users` collection.
- Ensure your selected `OPENAI_MODEL` supports image input.
