# config.py — настройки приложения через pydantic-settings
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# Файлы конфига в корне проекта: .envv (шаблон в репо), .env (секреты, переопределяет)
_ROOT_DIR = Path(__file__).resolve().parent
_ENV_FILES = (_ROOT_DIR / ".envv", _ROOT_DIR / ".env")

_ADMIN_ID_PLACEHOLDERS = ("ваш_telegram_id", "your_telegram_id")


class Settings(BaseSettings):
    """Конфигурация бота и БД из переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=[str(f) for f in _ENV_FILES if f.exists()] or [str(_ENV_FILES[0])],
        env_file_encoding="utf-8",
    )

    # Telegram
    BOT_TOKEN: str = Field(..., description="Токен бота от @BotFather")
    ADMIN_ID: int = Field(..., description="Telegram ID администратора для модерации")

    @field_validator("ADMIN_ID", mode="before")
    @classmethod
    def parse_admin_id(cls, v):
        if isinstance(v, int):
            return v
        s = (v or "").strip().lower()
        if s in _ADMIN_ID_PLACEHOLDERS or not s.isdigit():
            raise ValueError(
                "Укажите в .env числовой Telegram ID: ADMIN_ID=123456789. "
                "Узнать свой ID: напишите боту @userinfobot в Telegram."
            )
        return int(v)

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

    # Документы при регистрации: разрешённые типы и размер
    ALLOWED_DOCUMENT_EXTENSIONS: list[str] = Field(
        default=[".pdf", ".jpg", ".jpeg", ".png"],
        description="Расширения файлов для модерации (документы исполнителя)",
    )
    ALLOWED_DOCUMENT_MIME_PREFIXES: list[str] = Field(
        default=["application/pdf", "image/jpeg", "image/png"],
        description="Префиксы MIME для проверки типа документа",
    )
    MAX_DOCUMENT_SIZE_MB: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Максимальный размер файла при регистрации (МБ)",
    )

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
