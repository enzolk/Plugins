from __future__ import annotations

import datetime as dt
from typing import List

from ..app_context import app_ctx
from ..db import models


def list_appointments(start: dt.date, end: dt.date) -> List[models.Appointment]:
    with app_ctx.session() as session:
        return (
            session.query(models.Appointment)
            .filter(models.Appointment.start_dt >= start)
            .filter(models.Appointment.end_dt <= end)
            .order_by(models.Appointment.start_dt)
            .all()
        )


__all__ = ["list_appointments"]
