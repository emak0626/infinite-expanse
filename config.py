import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Kabu Station API
    KABU_API_PASSWORD: str = ""
    KABU_API_HOST: str = "localhost" # Set to 'host.docker.internal' in docker-compose
    KABU_API_PORT: int = 18080
    KABU_API_TOKEN: str = ""
    
    # Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_ID: str = "gemini-2.0-flash"

    # Web Authentication
    WEB_USERNAME: str = "admin"
    WEB_PASSWORD: str = "infinity"
    
    # Database Settings
    POSTGRES_USER: str = "user"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "stock_analysis"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    
    @property
    def DATABASE_URL(self) -> str:
        if os.getenv("USE_SQLITE", "True").lower() == "true":
            return "sqlite+aiosqlite:///./stock.db"
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Application Settings
    MOCK_MODE: bool = True
    WATCHLIST: list = [
        "7203", "9984", "6758", "8035", "5401", 
        "9101", "8306", "8316", "7267", "6501",
        "6702", "7751", "4502", "4503", "6954",
        "6098", "6367", "6861", "7974", "9432"
    ]

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()
