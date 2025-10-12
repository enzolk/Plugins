from __future__ import annotations

from typing import List

from sqlalchemy.orm import joinedload

from ..app_context import app_ctx
from ..db import models


def list_patients() -> List[models.Patient]:
    with app_ctx.session() as session:
        return session.query(models.Patient).order_by(models.Patient.last_name).all()


def get_patient(patient_id: int) -> models.Patient | None:
    with app_ctx.session() as session:
        return session.get(models.Patient, patient_id)


def create_patient(**kwargs) -> models.Patient:
    with app_ctx.session() as session:
        patient = models.Patient(**kwargs)
        session.add(patient)
        session.commit()
        session.refresh(patient)
        return patient


__all__ = ["list_patients", "get_patient", "create_patient"]
