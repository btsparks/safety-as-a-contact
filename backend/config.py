"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    environment: str = "development"
    secret_key: str = "dev-secret-change-in-production"
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite:///safety_as_a_contact.db"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_messaging_service_sid: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # SMS compliance
    max_messages_per_phone_per_day: int = 5
    sending_window_start: int = 8   # 8am
    sending_window_end: int = 21    # 9pm

    # Phone hashing
    phone_hash_salt: str = "change-this-salt-in-production"

    # Conversation session
    session_pause_minutes: int = 30     # pause after 30 min no reply
    session_timeout_minutes: int = 240  # new session after 4 hours

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
