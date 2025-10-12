from __future__ import annotations

import datetime as dt

from ..domain import reports


def summary(activity_code: str, start: dt.date, end: dt.date) -> reports.ActivitySummary:
    return reports.activity_summary(activity_code, start, end)


__all__ = ["summary"]
