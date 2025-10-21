from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Dict


@dataclass
class NumberingConfig:
    digits: int = 4
    reset_annually: bool = True


class NumberingService:
    def __init__(self, load_config: Callable[[], Dict], save_config: Callable[[Dict], None]):
        self._load_config = load_config
        self._save_config = save_config
        self._state = self._load_config()
        self._numbering = self._state.setdefault("numbering", {})

    def _persist(self) -> None:
        self._save_config(self._state)

    def _key(self, activity_code: str, year: int | None) -> str:
        if year is None:
            return f"{activity_code}-permanent"
        return f"{activity_code}-{year}"

    def next_invoice_number(
        self,
        activity_code: str,
        prefix: str,
        invoice_date: date,
        config: NumberingConfig | None = None,
    ) -> str:
        cfg = config or NumberingConfig()
        year = invoice_date.year if cfg.reset_annually else None
        key = self._key(activity_code, year)
        current = int(self._numbering.get(key, 0)) + 1
        self._numbering[key] = current
        self._persist()
        if cfg.reset_annually:
            return f"{prefix}{invoice_date.year}-{current:0{cfg.digits}d}"
        return f"{prefix}{current:0{cfg.digits}d}"

    def preview_next_number(
        self,
        activity_code: str,
        prefix: str,
        invoice_date: date,
        config: NumberingConfig | None = None,
    ) -> str:
        cfg = config or NumberingConfig()
        year = invoice_date.year if cfg.reset_annually else None
        key = self._key(activity_code, year)
        current = int(self._numbering.get(key, 0)) + 1
        if cfg.reset_annually:
            return f"{prefix}{invoice_date.year}-{current:0{cfg.digits}d}"
        return f"{prefix}{current:0{cfg.digits}d}"

    def reset_sequence(self, activity_code: str, year: int | None = None) -> None:
        key = self._key(activity_code, year)
        if key in self._numbering:
            del self._numbering[key]
            self._persist()


__all__ = ["NumberingService", "NumberingConfig"]
