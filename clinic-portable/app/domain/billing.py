from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List


def _to_decimal(value: float | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class InvoiceLine:
    label: str
    qty: Decimal
    price_ht: Decimal
    vat_rate: Decimal

    @classmethod
    def from_floats(cls, label: str, qty: float, price_ht: float, vat_rate: float) -> "InvoiceLine":
        return cls(
            label=label,
            qty=_to_decimal(qty),
            price_ht=_to_decimal(price_ht),
            vat_rate=_to_decimal(vat_rate) / Decimal("100"),
        )

    def totals(self) -> tuple[Decimal, Decimal, Decimal]:
        total_ht = _round(self.qty * self.price_ht)
        total_vat = _round(total_ht * self.vat_rate)
        total_ttc = total_ht + total_vat
        return total_ht, total_vat, total_ttc


@dataclass
class InvoiceTotals:
    total_ht: Decimal
    total_vat: Decimal
    total_ttc: Decimal

    def as_dict(self) -> dict:
        return {
            "total_ht": float(self.total_ht),
            "total_vat": float(self.total_vat),
            "total_ttc": float(self.total_ttc),
        }


@dataclass
class Payment:
    amount: Decimal


@dataclass
class PaymentSummary:
    total_paid: Decimal
    remaining: Decimal


def compute_invoice_totals(lines: Iterable[InvoiceLine]) -> InvoiceTotals:
    total_ht = Decimal("0")
    total_vat = Decimal("0")
    total_ttc = Decimal("0")
    for line in lines:
        ht, vat, ttc = line.totals()
        total_ht += ht
        total_vat += vat
        total_ttc += ttc
    return InvoiceTotals(_round(total_ht), _round(total_vat), _round(total_ttc))


def summarize_payments(total_due: float | Decimal, payments: Iterable[Payment]) -> PaymentSummary:
    total_due_dec = _round(_to_decimal(total_due))
    total_paid = Decimal("0")
    for payment in payments:
        total_paid += _to_decimal(payment.amount)
    total_paid = _round(total_paid)
    remaining = _round(total_due_dec - total_paid)
    return PaymentSummary(total_paid=total_paid, remaining=remaining)


__all__ = [
    "InvoiceLine",
    "InvoiceTotals",
    "Payment",
    "PaymentSummary",
    "compute_invoice_totals",
    "summarize_payments",
]
