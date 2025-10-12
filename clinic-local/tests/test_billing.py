from datetime import date

import pytest

from app.models import Activity, Consultation, ConsultationItem, InvoiceItem, Patient, Service
from app.services.billing import InvoiceLine, calculate_totals, invoice_from_consultation


def test_calculate_totals():
    lines = [
        InvoiceLine(label="Séance", qty=1, price_ht=60.0, vat_rate=0.0),
        InvoiceLine(label="Drainage", qty=2, price_ht=50.0, vat_rate=20.0),
    ]
    totals = calculate_totals(lines)
    assert totals.total_ht == 160.0
    assert totals.total_vat == 20.0
    assert totals.total_ttc == 180.0


@pytest.mark.asyncio
async def test_invoice_from_consultation(async_session):
    activity = Activity(code="OST", name="Ostéopathie", invoice_prefix="OST-", color="#1d4ed8")
    service = Service(activity=activity, code="CONSULT", name="Consult", price_ht=60.0, vat_rate=0.0)
    patient = Patient(first_name="Alice", last_name="Martin")
    consultation = Consultation(activity=activity, patient=patient, date=date.today())
    consultation.items.append(ConsultationItem(service=service, qty=1, price_ht=60.0, vat_rate=0.0))

    async_session.add_all([activity, service, patient, consultation])
    await async_session.flush()

    invoice = await invoice_from_consultation(async_session, consultation.id, date.today())
    await async_session.flush()

    assert invoice.number.startswith("OST-")
    assert pytest.approx(invoice.total_ht) == 60.0
    assert invoice.status == "brouillon"

