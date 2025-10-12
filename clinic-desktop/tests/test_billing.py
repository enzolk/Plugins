from __future__ import annotations

from decimal import Decimal

from app.domain.billing import LineItem, billing_calculator


def test_billing_totals_precision():
    items = [
        LineItem(label="Séance", qty=Decimal("1"), price_ht=Decimal("60"), vat_rate=Decimal("0")),
        LineItem(label="Drainage", qty=Decimal("2"), price_ht=Decimal("50"), vat_rate=Decimal("0.20"), discount=Decimal("0.10")),
    ]
    totals = billing_calculator.compute(items)
    assert totals.total_ht == Decimal("150.00")
    assert totals.total_vat == Decimal("18.00")
    assert totals.total_ttc == Decimal("168.00")
    assert totals.vat_breakdown["20%"] == Decimal("18.00")
