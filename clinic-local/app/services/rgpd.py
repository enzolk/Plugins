import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Invoice, Patient


async def export_patient_data(session: AsyncSession, patient_id: int) -> Path:
    patient = await session.scalar(select(Patient).where(Patient.id == patient_id))
    if not patient:
        raise ValueError("Patient introuvable")
    invoices = (await session.scalars(select(Invoice).where(Invoice.patient_id == patient_id))).all()

    export_dir = get_settings().exports_path
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / f"patient-{patient_id}.zip"

    data = {
        "patient": {
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "email": patient.email,
            "phone": patient.phone,
            "birthdate": patient.birthdate.isoformat() if patient.birthdate else None,
            "address": patient.address_json,
            "tags": patient.tags_json,
            "consent_rgpd": patient.consent_rgpd,
        },
        "invoices": [
            {
                "number": inv.number,
                "date": inv.date.isoformat(),
                "total_ht": inv.total_ht,
                "total_vat": inv.total_vat,
                "total_ttc": inv.total_ttc,
                "status": inv.status,
            }
            for inv in invoices
        ],
    }

    json_path = export_dir / f"patient-{patient_id}.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        archive.write(json_path, arcname=json_path.name)
        for invoice in invoices:
            if invoice.pdf_path:
                pdf_file = get_settings().base_path / invoice.pdf_path
                if pdf_file.exists():
                    archive.write(pdf_file, arcname=f"invoices/{pdf_file.name}")
    json_path.unlink(missing_ok=True)
    return target


async def anonymise_patient(session: AsyncSession, patient_id: int) -> None:
    patient = await session.scalar(select(Patient).where(Patient.id == patient_id))
    if not patient:
        raise ValueError("Patient introuvable")
    patient.first_name = "Anonyme"
    patient.last_name = f"Patient-{patient_id}"
    patient.email = None
    patient.phone = None
    patient.address_json = {}
    patient.tags_json = []
    session.add(patient)

