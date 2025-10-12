from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db
from ..templating import templates
from ..models import Activity, Appointment, Patient

router = APIRouter()


@router.get("/")
async def appointments_calendar(request: Request, db: AsyncSession = Depends(get_db), activity_id: Optional[int] = None):
    query = select(Appointment)
    if activity_id:
        query = query.where(Appointment.activity_id == activity_id)
    appointments = (await db.scalars(query.order_by(Appointment.start_dt))).all()
    activities = (await db.scalars(select(Activity))).all()
    return templates.TemplateResponse(
        "appointments/calendar.html",
        {"request": request, "appointments": appointments, "activities": activities},
    )


@router.post("/")
async def create_appointment(
    db: AsyncSession = Depends(get_db),
    activity_id: int = Form(...),
    patient_id: int = Form(...),
    start_dt: str = Form(...),
    end_dt: str = Form(...),
    title: str = Form(...),
    notes: str = Form(""),
):
    appointment = Appointment(
        activity_id=activity_id,
        patient_id=patient_id,
        start_dt=datetime.fromisoformat(start_dt),
        end_dt=datetime.fromisoformat(end_dt),
        title=title,
        notes=notes,
    )
    db.add(appointment)
    await db.flush()
    return RedirectResponse("/appointments", status_code=302)


@router.post("/{appointment_id}/delete")
async def delete_appointment(appointment_id: int, db: AsyncSession = Depends(get_db)):
    appointment = await db.scalar(select(Appointment).where(Appointment.id == appointment_id))
    if appointment:
        await db.delete(appointment)
    return RedirectResponse("/appointments", status_code=302)

