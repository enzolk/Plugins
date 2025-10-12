from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


@dataclass
class LineItem:
    label: str
    qty: Decimal
    price_ht: Decimal
    vat_rate: Decimal
    discount: Decimal = Decimal("0")

    def total_ht(self) -> Decimal:
        base = self.qty * self.price_ht
        if self.discount:
            base = base * (Decimal("1") - self.discount)
        return base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def total_vat(self) -> Decimal:
        return (self.total_ht() * self.vat_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def total_ttc(self) -> Decimal:
        return (self.total_ht() + self.total_vat()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class InvoiceTotals:
    total_ht: Decimal
    total_vat: Decimal
    total_ttc: Decimal
    vat_breakdown: dict[str, Decimal] = field(default_factory=dict)


class BillingCalculator:
    """Calcule les montants de facturation avec arrondis au centime."""

    def compute(self, items: Iterable[LineItem]) -> InvoiceTotals:
        total_ht = Decimal("0")
        total_vat = Decimal("0")
        vat_breakdown: dict[str, Decimal] = {}
        for item in items:
            line_ht = item.total_ht()
            line_vat = item.total_vat()
            total_ht += line_ht
            total_vat += line_vat
            key = f"{(item.vat_rate * Decimal('100')).quantize(Decimal('0'))}%"
            vat_breakdown[key] = vat_breakdown.get(key, Decimal("0")) + line_vat
        total_ttc = total_ht + total_vat
        return InvoiceTotals(
            total_ht=total_ht.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_vat=total_vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_ttc=total_ttc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            vat_breakdown={k: v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for k, v in vat_breakdown.items()},
        )


billing_calculator = BillingCalculator()


__all__ = ["LineItem", "InvoiceTotals", "BillingCalculator", "billing_calculator"]
