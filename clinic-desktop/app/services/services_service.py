from __future__ import annotations

from typing import List

from ..app_context import app_ctx
from ..db import models


def list_services(activity_id: int | None = None) -> List[models.Service]:
    with app_ctx.session() as session:
        query = session.query(models.Service).order_by(models.Service.name)
        if activity_id:
            query = query.filter(models.Service.activity_id == activity_id)
        return query.all()


__all__ = ["list_services"]
