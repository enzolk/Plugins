from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import func

from ..app_context import app_ctx
from ..db import models


@dataclass
class ActivitySummary:
    activity_code: str
    total_ht: float
    total_vat: float
    total_ttc: float
    invoices_count: int


def monthly_turnover(activity_code: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    with app_ctx.session() as session:
        query = (
            session.query(
                func.strftime("%Y-%m", models.Invoice.date).label("month"),
                func.sum(models.Invoice.total_ht).label("total_ht"),
                func.sum(models.Invoice.total_vat).label("total_vat"),
                func.sum(models.Invoice.total_ttc).label("total_ttc"),
            )
            .join(models.Activity, models.Invoice.activity_id == models.Activity.id)
            .filter(models.Activity.code == activity_code)
            .filter(models.Invoice.date >= start)
            .filter(models.Invoice.date <= end)
            .group_by("month")
            .order_by("month")
        )
        rows = query.all()
    return pd.DataFrame(rows, columns=["month", "total_ht", "total_vat", "total_ttc"]).fillna(0)


def activity_summary(activity_code: str, start: dt.date, end: dt.date) -> ActivitySummary:
    with app_ctx.session() as session:
        totals = (
            session.query(
                func.sum(models.Invoice.total_ht),
                func.sum(models.Invoice.total_vat),
                func.sum(models.Invoice.total_ttc),
                func.count(models.Invoice.id),
            )
            .join(models.Activity, models.Invoice.activity_id == models.Activity.id)
            .filter(models.Activity.code == activity_code)
            .filter(models.Invoice.date >= start)
            .filter(models.Invoice.date <= end)
            .one()
        )
    total_ht, total_vat, total_ttc, count = totals
    return ActivitySummary(
        activity_code=activity_code,
        total_ht=float(total_ht or 0),
        total_vat=float(total_vat or 0),
        total_ttc=float(total_ttc or 0),
        invoices_count=int(count or 0),
    )


__all__ = ["monthly_turnover", "activity_summary", "ActivitySummary"]
