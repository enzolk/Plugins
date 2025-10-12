from __future__ import annotations

from ..app_context import app_ctx
from ..db import models


def get_settings() -> models.Settings:
    with app_ctx.session() as session:
        settings = session.query(models.Settings).first()
        if not settings:
            settings = models.Settings()
            session.add(settings)
            session.commit()
            session.refresh(settings)
        return settings


def update_settings(**kwargs) -> models.Settings:
    with app_ctx.session() as session:
        settings = session.query(models.Settings).first()
        if not settings:
            settings = models.Settings()
        for key, value in kwargs.items():
            setattr(settings, key, value)
        session.add(settings)
        session.commit()
        session.refresh(settings)
        return settings


__all__ = ["get_settings", "update_settings"]
