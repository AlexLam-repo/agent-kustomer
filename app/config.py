from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    environment: str = "local"
    admin_secret: str = "change-me"

    # DB puede venir como URL completa (Railway) o por partes
    database_url: str = ""

    db_user: str = "root"
    db_password: str = "password"
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "agent_kustomer"

    openai_api_key: str = ""

    kustomer_api_key: str = ""
    kustomer_webhook_secret: str = ""
    kustomer_base_url: str = "https://api.kustomerapp.com"

    message_batch_window_seconds: float = 15.0
    message_batch_max_size: int = 10

    slack_webhook_url: str = ""

    def get_database_url(self) -> str:
        # Si viene DATABASE_URL directo de Railway, úsalo
        if self.database_url:
            # Railway da mysql://, necesitamos mysql+aiomysql://
            url = self.database_url
            if url.startswith("mysql://"):
                url = url.replace("mysql://", "mysql+aiomysql://", 1)
            if url.startswith("mysql+mysqlconnector://"):
                url = url.replace("mysql+mysqlconnector://", "mysql+aiomysql://", 1)
            return url
        # Si no, construir desde partes
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
