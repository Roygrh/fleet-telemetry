from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://fleet:fleet@localhost:5432/fleet_telemetry"

    model_config = {"env_file": ".env"}


settings = Settings()
