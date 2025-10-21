from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.orm import Session

from app.db.models import Patient
from app.security.crypto import CryptoManager, CryptoError


@dataclass
class PatientExport:
    patient: dict
    consultations: List[dict]
    invoices: List[dict]


def export_patient_data(
    session: Session,
    patient: Patient,
    paths,
    crypto: CryptoManager,
    output_path: Path,
) -> Path:
    del session  # not used but kept for interface compatibility
    output_path.parent.mkdir(parents=True, exist_ok=True)
    consultations = [
        {
            "id": c.id,
            "date": c.date.isoformat(),
            "status": c.status,
            "notes_internal": c.notes_internal,
            "items": [
                {
                    "label": item.label_override or (item.service.name if item.service else ""),
                    "qty": item.qty,
                    "price_ht": item.price_ht,
                    "vat_rate": item.vat_rate,
                }
                for item in c.items
            ],
        }
        for c in patient.consultations
    ]

    invoices = []
    for invoice in patient.invoices:
        invoices.append(
            {
                "id": invoice.id,
                "number": invoice.number,
                "date": invoice.date.isoformat(),
                "status": invoice.status,
                "totals": {
                    "ht": invoice.total_ht,
                    "vat": invoice.total_vat,
                    "ttc": invoice.total_ttc,
                },
                "payments": [
                    {
                        "date": payment.date.isoformat(),
                        "method": payment.method,
                        "amount": payment.amount,
                        "reference": payment.reference,
                    }
                    for payment in invoice.payments
                ],
                "pdf_path": invoice.pdf_path,
            }
        )

    try:
        notes = crypto.decrypt(patient.notes_encrypted) if crypto.is_unlocked() else ""
    except CryptoError:
        notes = ""

    export_data = PatientExport(
        patient={
            "id": patient.id,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "birthdate": patient.birthdate.isoformat() if patient.birthdate else None,
            "email": patient.email,
            "phone": patient.phone,
            "address": patient.address_json,
            "tags": patient.tags_json,
            "notes": notes,
        },
        consultations=consultations,
        invoices=invoices,
    )

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("patient.json", json.dumps(asdict(export_data), indent=2, ensure_ascii=False))
        for invoice in patient.invoices:
            if invoice.pdf_path:
                pdf_path = Path(invoice.pdf_path)
                if not pdf_path.is_absolute():
                    pdf_path = paths.files_dir / invoice.pdf_path
                if pdf_path.exists():
                    arcname = f"pdfs/invoice_{invoice.number}.pdf"
                    archive.write(pdf_path, arcname=arcname)
    return output_path


def anonymize_patient(session: Session, patient: Patient) -> Patient:
    patient.first_name = "Patient"
    patient.last_name = f"Anonyme-{patient.id}"
    patient.email = None
    patient.phone = None
    patient.address_json = None
    patient.tags_json = json.dumps(["Anonymisé"])
    patient.notes_encrypted = None
    session.add(patient)
    return patient


__all__ = ["export_patient_data", "anonymize_patient"]
