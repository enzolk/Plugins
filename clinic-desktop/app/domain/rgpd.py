from __future__ import annotations

import json
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from ..app_context import app_ctx
from ..db import models


@dataclass
class PatientExport:
    patient: dict
    invoices: list[dict]


def export_patient_data(patient_id: int, target: Path) -> Path:
    with app_ctx.session() as session:
        patient = session.get(models.Patient, patient_id)
        if not patient:
            raise ValueError("Patient introuvable")
        invoices = (
            session.query(models.Invoice)
            .filter(models.Invoice.patient_id == patient_id)
            .all()
        )
    export = PatientExport(
        patient={
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "email": patient.email,
            "phone": patient.phone,
            "tags": patient.tags_json or [],
        },
        invoices=[
            {
                "number": invoice.number,
                "date": invoice.date.isoformat(),
                "total_ttc": invoice.total_ttc,
            }
            for invoice in invoices
        ],
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("patient.json", json.dumps(asdict(export), ensure_ascii=False, indent=2))
        files_dir = app_ctx.paths.root / "files"
        for invoice in invoices:
            if invoice.pdf_path:
                pdf_path = files_dir / invoice.pdf_path
                if pdf_path.exists():
                    archive.write(pdf_path, arcname=f"pdfs/{pdf_path.name}")
    return target


def anonymize_patient(patient_id: int) -> None:
    with app_ctx.session() as session:
        patient = session.get(models.Patient, patient_id)
        if not patient:
            raise ValueError("Patient introuvable")
        patient.first_name = "Anonyme"
        patient.last_name = f"ID{patient.id}"
        patient.email = None
        patient.phone = None
        patient.address_json = None
        patient.tags_json = []
        patient.notes_encrypted = None
        session.add(patient)
        session.commit()


__all__ = ["export_patient_data", "anonymize_patient"]
