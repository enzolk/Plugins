from __future__ import annotations

from typing import List

from ..app_context import app_ctx
from ..db import models


def list_activities() -> List[models.Activity]:
    with app_ctx.session() as session:
        return session.query(models.Activity).order_by(models.Activity.name).all()


def get_activity_by_code(code: str) -> models.Activity | None:
    with app_ctx.session() as session:
        return session.query(models.Activity).filter(models.Activity.code == code).first()


__all__ = ["list_activities", "get_activity_by_code"]
