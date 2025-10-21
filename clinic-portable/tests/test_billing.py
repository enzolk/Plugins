from decimal import Decimal

from app.domain.billing import InvoiceLine, compute_invoice_totals, summarize_payments, Payment


def test_compute_invoice_totals():
    lines = [
        InvoiceLine.from_floats("Consultation", 1, 50.0, 0.0),
        InvoiceLine.from_floats("Drainage", 2, 80.0, 20.0),
    ]
    totals = compute_invoice_totals(lines)
    assert totals.total_ht == Decimal("210.00")
    assert totals.total_vat == Decimal("32.00")
    assert totals.total_ttc == Decimal("242.00")


def test_summarize_payments():
    payments = [Payment(amount=Decimal("100.00")), Payment(amount=Decimal("40.00"))]
    summary = summarize_payments(Decimal("180.00"), payments)
    assert summary.total_paid == Decimal("140.00")
    assert summary.remaining == Decimal("40.00")
