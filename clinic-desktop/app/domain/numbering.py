from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from ..app_context import app_ctx
from ..db import models


@dataclass
class NumberingConfig:
    activity_code: str
    prefix: str
    year: int
    next_seq: int
    reset_yearly: bool = True


class NumberingService:
    """Gère la numérotation indépendante des factures par activité."""

    def __init__(self) -> None:
        self._cache: dict[str, NumberingConfig] = {}

    def _load_activity(self, activity_code: str) -> NumberingConfig:
        with app_ctx.session() as session:
            activity = (
                session.query(models.Activity)
                .filter(models.Activity.code == activity_code)
                .first()
            )
            if not activity:
                raise ValueError(f"Activité inconnue: {activity_code}")
            config = NumberingConfig(
                activity_code=activity.code,
                prefix=activity.invoice_prefix,
                year=dt.date.today().year,
                next_seq=activity.next_seq,
                reset_yearly=True,
            )
            self._cache[activity_code] = config
            return config

    def next_invoice_number(self, activity_code: str, *, date: dt.date | None = None) -> str:
        today = date or dt.date.today()
        config = self._cache.get(activity_code) or self._load_activity(activity_code)
        if config.reset_yearly and config.year != today.year:
            config.year = today.year
            config.next_seq = 1
        number = f"{config.prefix}{today.year:04d}-{config.next_seq:04d}"
        config.next_seq += 1
        self._persist(activity_code, config.next_seq, config.year)
        return number

    def _persist(self, activity_code: str, seq: int, year: int) -> None:
        with app_ctx.session() as session:
            activity = (
                session.query(models.Activity)
                .filter(models.Activity.code == activity_code)
                .first()
            )
            if not activity:
                raise ValueError(f"Activité inconnue: {activity_code}")
            activity.next_seq = seq
            session.add(activity)
            session.commit()


numbering_service = NumberingService()


__all__ = ["numbering_service", "NumberingService", "NumberingConfig"]
