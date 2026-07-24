from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "LiveOS API"
    APP_ENV: str = "development"

    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str
    OPENAI_MODEL: str

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

