from __future__ import annotations

import datetime as dt
from decimal import Decimal

from app.domain.billing import LineItem
from app.domain.pdf import InvoiceDocument, generate_invoice_pdf


def test_generate_invoice_pdf(tmp_path):
    doc = InvoiceDocument(
        activity_name="Ostéopathie",
        activity_code="OST",
        invoice_number="OST-2024-0001",
        invoice_date=dt.date(2024, 1, 10),
        patient_name="Alice Dupont",
        lines=[
            LineItem(label="Séance", qty=Decimal("1"), price_ht=Decimal("60"), vat_rate=Decimal("0")),
            LineItem(label="Drainage", qty=Decimal("1"), price_ht=Decimal("50"), vat_rate=Decimal("0.20")),
        ],
        notes="Merci pour votre confiance",
    )
    path = tmp_path / "facture.pdf"
    generate_invoice_pdf(doc, path)
    assert path.exists()
    assert path.stat().st_size > 1000
