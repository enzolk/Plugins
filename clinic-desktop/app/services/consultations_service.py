from __future__ import annotations

from typing import List

from ..app_context import app_ctx
from ..db import models


def list_consultations() -> List[models.Consultation]:
    with app_ctx.session() as session:
        return session.query(models.Consultation).order_by(models.Consultation.date.desc()).all()


__all__ = ["list_consultations"]
