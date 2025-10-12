from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..dependencies import get_db
from ..templating import templates
from ..models import Activity, Invoice, PaymentMethod, Settings as SettingsModel
from ..services import billing, pdf

router = APIRouter()


@router.get("/")
async def invoices_list(request: Request, db: AsyncSession = Depends(get_db)):
    invoices = (await db.scalars(select(Invoice).order_by(Invoice.date.desc()))).all()
    return templates.TemplateResponse(
        "invoices/list.html",
        {"request": request, "invoices": invoices},
    )


@router.post("/from-consultation")
async def invoice_from_consultation(
    consultation_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    invoice = await billing.invoice_from_consultation(db, consultation_id)
    await db.flush()
    return RedirectResponse(f"/invoices/{invoice.id}", status_code=302)


@router.get("/{invoice_id}")
async def invoice_detail(invoice_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    invoice = await db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.items),
            selectinload(Invoice.payments),
            selectinload(Invoice.patient),
            selectinload(Invoice.activity),
        )
    )
    if not invoice:
        return RedirectResponse("/invoices", status_code=302)
    return templates.TemplateResponse(
        "invoices/detail.html",
        {"request": request, "invoice": invoice},
    )


@router.post("/{invoice_id}/payments")
async def add_payment(
    invoice_id: int,
    amount: float = Form(...),
    method: PaymentMethod = Form(...),
    payment_date: Optional[date] = Form(None),
    ref: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    invoice = await db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.items),
            selectinload(Invoice.payments),
            selectinload(Invoice.patient),
            selectinload(Invoice.activity),
        )
    )
    if not invoice:
        return RedirectResponse("/invoices", status_code=302)
    await billing.record_payment(db, invoice, amount=amount, method=method, payment_date=payment_date, ref=ref)
    await db.flush()
    return RedirectResponse(f"/invoices/{invoice_id}", status_code=302)


@router.get("/{invoice_id}/pdf")
async def invoice_pdf(invoice_id: int, db: AsyncSession = Depends(get_db)):
    invoice = await db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.items),
            selectinload(Invoice.payments),
            selectinload(Invoice.patient),
            selectinload(Invoice.activity),
        )
    )
    if not invoice:
        return RedirectResponse("/invoices", status_code=302)
    settings = await db.scalar(select(SettingsModel).limit(1))
    activity = invoice.activity
    patient = invoice.patient
    target = pdf.render_invoice_pdf(invoice, patient, activity, settings, list(invoice.items))
    return FileResponse(target)
