from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.domain.billing import InvoiceLine, compute_invoice_totals
from app.domain.numbering import NumberingConfig, NumberingService
from app.security.crypto import CryptoManager

from .models import (
    Activity,
    Appointment,
    Consultation,
    ConsultationItem,
    Invoice,
    InvoiceItem,
    Patient,
    Payment,
    Service,
    Settings,
)

DEFAULT_MASTER_PASSWORD = "demo-master"


def seed_demo_data(session: Session, crypto: CryptoManager) -> None:
    if session.query(Activity).count() > 0:
        return

    crypto.ensure_master_key(DEFAULT_MASTER_PASSWORD)
    crypto.unlock(DEFAULT_MASTER_PASSWORD)

    settings = Settings(
        org_name="Cabinet Demo",
        siret="12345678900011",
        vat_number="FR00123456789",
        address_json=json.dumps(
            {
                "line1": "10 Rue de la Paix",
                "zip": "75002",
                "city": "Paris",
                "country": "France",
            }
        ),
        iban_bic="FR761111900069410000AA33222 / AGRIFRPP",
        legal_footer_text="Profession libérale soumise à la TVA.",
        fiscal_year_start_month=1,
    )
    session.add(settings)

    activities = [
        Activity(
            code="OST",
            name="Ostéopathie",
            color="#2F80ED",
            default_vat_rate=0.0,
            invoice_prefix="OST-",
            revenue_account="7061",
            pdf_header_html="<h2>Cabinet d'ostéopathie</h2>",
            pdf_footer_html="<p>Merci pour votre confiance.</p>",
        ),
        Activity(
            code="DRL",
            name="Drainage lymphatique",
            color="#27AE60",
            default_vat_rate=20.0,
            invoice_prefix="DRL-",
            revenue_account="7062",
            pdf_header_html="<h2>Drainage lymphatique</h2>",
            pdf_footer_html="<p>Merci pour votre confiance.</p>",
        ),
    ]
    session.add_all(activities)
    session.flush()

    services_data = {
        "OST": [
            ("CONSULT", "Consultation ostéopathique", 45, 50.0, 0.0),
            ("REHAB", "Rééducation fonctionnelle", 30, 35.0, 0.0),
            ("URGENCE", "Urgence ostéo", 30, 60.0, 0.0),
        ],
        "DRL": [
            ("DRAIN30", "Drainage 30 min", 30, 45.0, 20.0),
            ("DRAIN60", "Drainage 60 min", 60, 80.0, 20.0),
            ("FORFAIT", "Forfait 5 séances", 60, 350.0, 20.0),
        ],
    }

    services = {}
    for activity in activities:
        for code, name, duration, price, vat in services_data[activity.code]:
            service = Service(
                activity_id=activity.id,
                code=code,
                name=name,
                default_duration_min=duration,
                price_ht=price,
                vat_rate=vat,
                description="Service de démonstration",
            )
            session.add(service)
            services[(activity.code, code)] = service
    session.flush()

    patients = [
        Patient(
            first_name="Alice",
            last_name="Martin",
            birthdate=date(1985, 6, 15),
            email="alice@example.com",
            phone="0601020304",
            address_json=json.dumps({"line1": "1 Rue Demo", "zip": "75001", "city": "Paris"}),
            tags_json=json.dumps(["Ostéo"]),
            notes_encrypted=crypto.encrypt("Note confidentielle Alice"),
            consent_rgpd=True,
        ),
        Patient(
            first_name="Bruno",
            last_name="Durand",
            birthdate=date(1978, 9, 3),
            email="bruno@example.com",
            phone="0605060708",
            address_json=json.dumps({"line1": "5 Rue Demo", "zip": "69002", "city": "Lyon"}),
            tags_json=json.dumps(["Drainage"]),
            notes_encrypted=crypto.encrypt("Suivi post-opératoire"),
            consent_rgpd=True,
        ),
        Patient(
            first_name="Chloé",
            last_name="Petit",
            birthdate=date(1992, 1, 20),
            email="chloe@example.com",
            phone="0611121314",
            address_json=json.dumps({"line1": "12 Avenue Exemple", "zip": "31000", "city": "Toulouse"}),
            tags_json=json.dumps(["Ostéo", "Drainage"]),
            notes_encrypted=crypto.encrypt("Sportive de haut niveau"),
            consent_rgpd=False,
        ),
        Patient(
            first_name="David",
            last_name="Leroy",
            birthdate=date(1969, 12, 5),
            email="david@example.com",
            phone="0699887766",
            address_json=json.dumps({"line1": "8 Rue Test", "zip": "44000", "city": "Nantes"}),
            tags_json=json.dumps(["Drainage"]),
            notes_encrypted=crypto.encrypt("Suivi lymphatique"),
            consent_rgpd=True,
        ),
    ]
    session.add_all(patients)
    session.flush()

    now = datetime.now()
    for idx, patient in enumerate(patients):
        activity = activities[idx % len(activities)]
        session.add(
            Appointment(
                activity_id=activity.id,
                patient_id=patient.id,
                start_dt=now + timedelta(days=idx),
                end_dt=now + timedelta(days=idx, hours=1),
                title=f"Séance {activity.code}",
                notes="Rendez-vous de démonstration",
                status="confirmed",
            )
        )
        consultation = Consultation(
            activity_id=activity.id,
            patient_id=patient.id,
            date=now - timedelta(days=30 - idx),
            notes_internal="Consultation pré-facturation",
            status="billed",
        )
        session.add(consultation)
        service_code = "CONSULT" if activity.code == "OST" else "DRAIN60"
        service = services[(activity.code, service_code)]
        session.add(
            ConsultationItem(
                consultation=consultation,
                service_id=service.id,
                qty=1,
                price_ht=service.price_ht,
                vat_rate=service.vat_rate,
                label_override=service.name,
            )
        )
    session.flush()

    config_loader = lambda: {}  # type: ignore
    config_saver = lambda cfg: None  # type: ignore
    numbering = NumberingService(config_loader, config_saver)

    invoices_to_create = [
        (activities[0], patients[0], [(services[("OST", "CONSULT")], 1)], [("Carte", 50.0)], True),
        (activities[0], patients[2], [(services[("OST", "URGENCE")], 1)], [], False),
        (activities[1], patients[1], [(services[("DRL", "DRAIN60")], 1)], [("Virement", 96.0)], True),
        (activities[1], patients[3], [(services[("DRL", "FORFAIT")], 1)], [("Chèque", 150.0)], False),
    ]

    for activity, patient, service_lines, payments_data, paid in invoices_to_create:
        invoice_date = now - timedelta(days=10)
        number = numbering.next_invoice_number(
            activity.code, activity.invoice_prefix, invoice_date.date(), NumberingConfig()
        )
        invoice = Invoice(
            activity_id=activity.id,
            patient_id=patient.id,
            date=invoice_date,
            number=number,
            status="paid" if paid else "sent",
            currency="EUR",
        )
        session.add(invoice)
        items = []
        for service, qty in service_lines:
            line = InvoiceLine.from_floats(service.name, qty, service.price_ht, service.vat_rate)
            ht, vat, ttc = line.totals()
            item = InvoiceItem(
                invoice=invoice,
                label=service.name,
                qty=float(qty),
                price_ht=float(service.price_ht),
                vat_rate=float(service.vat_rate),
                total_ht=float(ht),
                total_vat=float(vat),
                total_ttc=float(ttc),
                service_id_nullable=service.id,
            )
            session.add(item)
            items.append(line)
        totals = compute_invoice_totals(items)
        invoice.total_ht = float(totals.total_ht)
        invoice.total_vat = float(totals.total_vat)
        invoice.total_ttc = float(totals.total_ttc)

        for method, amount in payments_data:
            payment = Payment(
                invoice=invoice,
                method=method,
                amount=amount,
                date=invoice_date,
            )
            session.add(payment)
