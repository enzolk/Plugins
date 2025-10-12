from __future__ import annotations

import json
from typing import Dict

from fastapi import Request
from markupsafe import Markup
from starlette.templating import Jinja2Templates

from .config import get_settings

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.template_path))
_locale_cache: Dict[str, str] | None = None


def load_locale() -> Dict[str, str]:
    global _locale_cache
    if _locale_cache is None:
        locale_file = settings.locale_path / f"{settings.locale}.json"
        if locale_file.exists():
            _locale_cache = json.loads(locale_file.read_text(encoding="utf-8"))
        else:
            _locale_cache = {}
    return _locale_cache


def translate(key: str) -> str:
    data = load_locale()
    return data.get(key, key)


def csrf_input(request: Request) -> Markup:
    token = request.session.get("csrf_token", "")
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}" />')


templates.env.globals["t"] = translate
templates.env.globals["csrf_input"] = csrf_input

