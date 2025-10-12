from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Iterable, List

from ..app_context import app_ctx
from ..db import models
from ..domain import pdf as pdf_domain
from ..domain.billing import LineItem
from ..domain.numbering import numbering_service


def list_invoices(activity_code: str | None = None) -> List[models.Invoice]:
    with app_ctx.session() as session:
        query = session.query(models.Invoice).order_by(models.Invoice.date.desc())
        if activity_code:
            query = query.join(models.Activity).filter(models.Activity.code == activity_code)
        return query.all()


def create_invoice(
    activity_code: str,
    patient: models.Patient,
    items: Iterable[LineItem],
    date: dt.date | None = None,
) -> models.Invoice:
    date = date or dt.date.today()
    number = numbering_service.next_invoice_number(activity_code, date=date)
    totals = [item for item in items]
    calculator_totals = pdf_domain.billing_calculator.compute(totals)
    with app_ctx.session() as session:
        activity = (
            session.query(models.Activity)
            .filter(models.Activity.code == activity_code)
            .first()
        )
        if not activity:
            raise ValueError("Activité introuvable")
        invoice = models.Invoice(
            activity_id=activity.id,
            patient_id=patient.id,
            date=date,
            number=number,
            total_ht=float(calculator_totals.total_ht),
            total_vat=float(calculator_totals.total_vat),
            total_ttc=float(calculator_totals.total_ttc),
            status="issued",
        )
        session.add(invoice)
        session.commit()
        session.refresh(invoice)
    return invoice


def generate_invoice_pdf(invoice: models.Invoice, items: Iterable[LineItem]) -> Path:
    doc = pdf_domain.InvoiceDocument(
        activity_name="Facture",
        activity_code="GEN",
        invoice_number=invoice.number,
        invoice_date=invoice.date,
        patient_name=str(invoice.patient_id),
        lines=list(items),
    )
    path = app_ctx.paths.files_dir / "invoices" / str(invoice.date.year) / f"{invoice.number}.pdf"
    return pdf_domain.generate_invoice_pdf(doc, path)


__all__ = ["list_invoices", "create_invoice", "generate_invoice_pdf"]
