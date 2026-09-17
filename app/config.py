from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- database ---
    mongodb_uri: str = "mongodb://localhost:27017"
    db_name: str = "femto"

    # --- auth ---
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    # --- cors ---
    cors_origins: str = "http://localhost:5173"

    # --- artifact storage (Azure Blob) ---
    azure_storage_connection_string: str = ""
    blob_container: str = "femto-artifacts"
    download_url_minutes: int = 10

    # --- billing (Stripe) ---
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    price_single_unlock_cents: int = 900        # $9 to unlock one artifact
    price_credit_pack_cents: int = 4900         # $49 for a 10-unlock pack
    credit_pack_size: int = 10
    checkout_success_url: str = "http://localhost:5173/#/dashboard"
    checkout_cancel_url: str = "http://localhost:5173/#/dashboard"

    # --- github oauth ---
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/github/callback"
    # Fernet key used to encrypt stored GitHub tokens at rest.
    token_encryption_key: str = ""

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
