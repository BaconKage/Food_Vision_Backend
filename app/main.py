import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.config import get_settings
from app.routers.food_scan import router as food_scan_router

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title=settings.app_name)
app.include_router(food_scan_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.exception_handler(PyMongoError)
async def mongo_exception_handler(_, exc: PyMongoError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"ok": False, "detail": f"Database error: {exc}"})
