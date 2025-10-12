from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    Consultation,
    ConsultationItem,
    Invoice,
    InvoiceItem,
    Patient,
    Payment,
    PaymentMethod,
)
from .numbering import next_invoice_number


@dataclass
class InvoiceLine:
    label: str
    qty: int
    price_ht: float
    vat_rate: float
    service_id: Optional[int] = None

    @property
    def total_ht(self) -> float:
        return float(Decimal(self.price_ht * self.qty).quantize(Decimal("0.01"), ROUND_HALF_UP))

    @property
    def total_vat(self) -> float:
        vat = Decimal(self.total_ht) * Decimal(self.vat_rate / 100)
        return float(vat.quantize(Decimal("0.01"), ROUND_HALF_UP))

    @property
    def total_ttc(self) -> float:
        return float((Decimal(self.total_ht) + Decimal(self.total_vat)).quantize(Decimal("0.01"), ROUND_HALF_UP))


@dataclass
class InvoiceTotals:
    total_ht: float
    total_vat: float
    total_ttc: float


def calculate_totals(lines: Iterable[InvoiceLine]) -> InvoiceTotals:
    total_ht = Decimal("0")
    total_vat = Decimal("0")
    for line in lines:
        total_ht += Decimal(line.total_ht)
        total_vat += Decimal(line.total_vat)
    total_ttc = total_ht + total_vat
    return InvoiceTotals(
        float(total_ht.quantize(Decimal("0.01"), ROUND_HALF_UP)),
        float(total_vat.quantize(Decimal("0.01"), ROUND_HALF_UP)),
        float(total_ttc.quantize(Decimal("0.01"), ROUND_HALF_UP)),
    )


async def invoice_from_consultation(
    session: AsyncSession,
    consultation_id: int,
    invoice_date: Optional[date] = None,
) -> Invoice:
    consultation = await session.scalar(
        select(Consultation)
        .where(Consultation.id == consultation_id)
        .options(selectinload(Consultation.items).selectinload(ConsultationItem.service))
    )
    if not consultation:
        raise ValueError("Consultation introuvable")

    invoice_date = invoice_date or date.today()
    number = await next_invoice_number(session, consultation.activity_id, invoice_date)

    invoice = Invoice(
        activity_id=consultation.activity_id,
        patient_id=consultation.patient_id,
        date=invoice_date,
        number=number,
        status="brouillon",
    )
    session.add(invoice)

    lines: List[InvoiceLine] = []
    for item in consultation.items:
        label = item.label_override or item.service.name
        line = InvoiceLine(
            label=label,
            qty=item.qty,
            price_ht=item.price_ht,
            vat_rate=item.vat_rate,
            service_id=item.service_id,
        )
        lines.append(line)
        invoice_item = InvoiceItem(
            label=line.label,
            qty=line.qty,
            price_ht=line.price_ht,
            vat_rate=line.vat_rate,
            total_ht=line.total_ht,
            total_vat=line.total_vat,
            total_ttc=line.total_ttc,
            service_id=line.service_id,
        )
        invoice.items.append(invoice_item)

    totals = calculate_totals(lines)
    invoice.total_ht = totals.total_ht
    invoice.total_vat = totals.total_vat
    invoice.total_ttc = totals.total_ttc
    consultation.status = "facturé"
    return invoice


async def record_payment(
    session: AsyncSession,
    invoice: Invoice,
    amount: float,
    method: PaymentMethod,
    payment_date: Optional[date] = None,
    ref: Optional[str] = None,
) -> Payment:
    payment = Payment(
        invoice_id=invoice.id,
        date=payment_date or date.today(),
        method=method,
        amount=amount,
        ref=ref,
    )
    session.add(payment)
    paid = sum(p.amount for p in invoice.payments) + amount
    if paid >= invoice.total_ttc - 0.01:
        invoice.status = "payé"
    else:
        invoice.status = "partiel"
    await session.flush()
    return payment


async def ensure_patient(session: AsyncSession, patient_id: int) -> Patient:
    patient = await session.scalar(select(Patient).where(Patient.id == patient_id))
    if not patient:
        raise ValueError("Patient introuvable")
    return patient

