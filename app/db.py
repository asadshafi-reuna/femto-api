from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

# Lazily-created singleton client. Importing this module does NOT open a
# connection — the client only dials MongoDB on first real use — so the app
# can be imported and unit-tested without a running database.
_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=3000,
        )
    return _client


def get_db():
    return get_client()[settings.db_name]


async def ensure_indexes() -> None:
    """Create the indexes the app relies on. Called on startup; failures are
    non-fatal so the server still boots if the DB is briefly unreachable."""
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.conversions.create_index([("user_id", 1), ("created_at", -1)])
