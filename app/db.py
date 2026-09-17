from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)
    return _client


def get_db():
    return get_client()[settings.db_name]


async def ensure_indexes() -> None:
    """Indexes the app relies on. Safe to run on every start."""
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.users.create_index("github.login")

    await db.conversions.create_index([("user_id", 1), ("created_at", -1)])
    await db.conversions.create_index([("user_id", 1), ("status", 1)])

    await db.orders.create_index([("user_id", 1), ("created_at", -1)])
    await db.orders.create_index("provider_ref")

    # OAuth states expire on their own after 10 minutes.
    await db.oauth_states.create_index("created_at", expireAfterSeconds=600)
    await db.oauth_states.create_index("state", unique=True)
