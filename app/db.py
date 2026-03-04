from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import get_settings


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    settings = get_settings()
    return MongoClient(settings.mongodb_uri, tz_aware=True)


@lru_cache(maxsize=1)
def get_db() -> Database:
    settings = get_settings()
    return get_client()[settings.mongodb_db_name]


def users_collection() -> Collection:
    return get_db()["users"]


def foods_collection() -> Collection:
    return get_db()["foods"]


def mealplans_collection() -> Collection:
    return get_db()["mealplans"]
