from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db
from ..templating import templates
from ..models import Activity, Consultation, ConsultationItem, Patient, Service

router = APIRouter()


@router.get("/")
async def consultations_list(request: Request, db: AsyncSession = Depends(get_db)):
    consultations = (await db.scalars(select(Consultation).order_by(Consultation.date.desc()))).all()
    return templates.TemplateResponse(
        "consultations/list.html",
        {"request": request, "consultations": consultations},
    )


@router.get("/new")
async def consultation_form(request: Request, db: AsyncSession = Depends(get_db), patient_id: Optional[int] = None):
    patients = (await db.scalars(select(Patient))).all()
    activities = (await db.scalars(select(Activity))).all()
    services = (await db.scalars(select(Service))).all()
    return templates.TemplateResponse(
        "consultations/form.html",
        {
            "request": request,
            "patients": patients,
            "activities": activities,
            "services": services,
            "patient_id": patient_id,
        },
    )


@router.post("/")
async def create_consultation(
    db: AsyncSession = Depends(get_db),
    patient_id: int = Form(...),
    activity_id: int = Form(...),
    service_id: int = Form(...),
    qty: int = Form(1),
    price_ht: float = Form(...),
    vat_rate: float = Form(...),
    notes_internal: str = Form(""),
):
    consultation = Consultation(
        patient_id=patient_id,
        activity_id=activity_id,
        date=date.today(),
        notes_internal=notes_internal,
    )
    item = ConsultationItem(
        service_id=service_id,
        qty=qty,
        price_ht=price_ht,
        vat_rate=vat_rate,
    )
    consultation.items.append(item)
    db.add(consultation)
    await db.flush()
    return RedirectResponse("/consultations", status_code=302)

