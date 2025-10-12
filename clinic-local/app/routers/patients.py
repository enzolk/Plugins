from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db
from ..templating import templates
from ..models import Patient
from ..security import decrypt_text, encrypt_text

router = APIRouter()


@router.get("/")
async def patients_list(request: Request, db: AsyncSession = Depends(get_db), q: Optional[str] = None):
    query = select(Patient)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                Patient.email.ilike(like),
            )
        )
    patients = (await db.scalars(query.order_by(Patient.last_name))).all()
    return templates.TemplateResponse(
        "patients/list.html",
        {"request": request, "patients": patients, "query": q or ""},
    )


@router.get("/new")
async def patient_form(request: Request):
    return templates.TemplateResponse("patients/form.html", {"request": request, "patient": None})


@router.post("/")
async def create_patient(
    request: Request,
    db: AsyncSession = Depends(get_db),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    notes: Optional[str] = Form(""),
    consent_rgpd: Optional[str] = Form(None),
):
    patient = Patient(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        notes_encrypted=encrypt_text(notes or ""),
        consent_rgpd=consent_rgpd is not None,
    )
    db.add(patient)
    await db.flush()
    return RedirectResponse(f"/patients/{patient.id}", status_code=302)


@router.get("/{patient_id}")
async def patient_detail(patient_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    patient = await db.scalar(select(Patient).where(Patient.id == patient_id))
    if not patient:
        return RedirectResponse("/patients", status_code=302)
    notes = decrypt_text(patient.notes_encrypted)
    return templates.TemplateResponse(
        "patients/detail.html",
        {"request": request, "patient": patient, "notes": notes},
    )

