from __future__ import annotations

import datetime as dt
from typing import List

from ..app_context import app_ctx
from ..db import models


def record_payment(invoice_id: int, amount: float, method: str, reference: str | None = None) -> models.Payment:
    with app_ctx.session() as session:
        payment = models.Payment(
            invoice_id=invoice_id,
            amount=amount,
            method=method,
            reference=reference,
            date=dt.date.today(),
        )
        session.add(payment)
        session.commit()
        session.refresh(payment)
        return payment


def list_payments(invoice_id: int) -> List[models.Payment]:
    with app_ctx.session() as session:
        return (
            session.query(models.Payment)
            .filter(models.Payment.invoice_id == invoice_id)
            .order_by(models.Payment.date)
            .all()
        )


__all__ = ["record_payment", "list_payments"]
