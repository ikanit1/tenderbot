# config.py — настройки приложения через pydantic-settings
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Конфигурация бота и БД из переменных окружения."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Telegram
    BOT_TOKEN: str = Field(..., description="Токен бота от @BotFather")
    ADMIN_ID: int = Field(..., description="Telegram ID администратора для модерации")

    # PostgreSQL
    DATABASE_URL: str = Field(
        ...,
        description="URL подключения к PostgreSQL (async). Пример: postgresql+asyncpg://user:pass@host:5432/db",
    )

    # Веб-админка (опционально)
    WEB_SECRET_KEY: str = Field(
        default="change-me-in-production",
        description="Секрет для сессий веб-админки",
    )
    ADMIN_PASSWORD: str = Field(
        default="admin",
        description="Пароль входа в веб-админку (логин: admin)",
    )
    WEB_HOST: str = Field(default="0.0.0.0", description="Хост для веб-сервера")
    WEB_PORT: int = Field(default=8000, description="Порт веб-сервера")

    # Список доступных навыков (категорий тендеров)
    SKILL_TAGS: list[str] = Field(
        default=[
            "СКУД",
            "Видеонаблюдение",
            "АПС",
            "Электромонтаж",
            "Слаботочные системы",
            "Сетевое оборудование",
        ],
        description="Теги навыков для выбора при регистрации и создания тендеров",
    )


settings = Settings()
