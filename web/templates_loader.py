# web/templates_loader.py — Единый загрузчик шаблонов с фильтрами
from pathlib import Path
from fastapi.templating import Jinja2Templates
from web.utils.translations import (
    translate_status, translate_role, translate_field,
    humanize_status, humanize_role, format_datetime, format_date,
)

# Создаем единый экземпляр Jinja2Templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates", autoescape=True)

# Регистрируем фильтры для перевода
templates.env.filters["translate_status"] = translate_status
templates.env.filters["translate_role"] = translate_role
templates.env.filters["translate_field"] = translate_field
templates.env.filters["humanize_status"] = humanize_status
templates.env.filters["humanize_role"] = humanize_role
templates.env.filters["format_datetime"] = format_datetime
templates.env.filters["format_date"] = format_date
