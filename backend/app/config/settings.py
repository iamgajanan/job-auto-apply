from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    APP_NAME: str

    DATABASE_URL: str

    REDIS_URL: str

    JWT_SECRET: str

    BACKEND_HOST: str

    BACKEND_PORT: int

    APP_ENV: str

    class Config:
        env_file = "../../.env"


settings = Settings()