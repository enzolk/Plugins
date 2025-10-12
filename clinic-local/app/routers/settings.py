from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db
from ..templating import templates
from ..models import Activity, Service, Settings as SettingsModel

router = APIRouter()


@router.get("/")
async def settings_index(request: Request, db: AsyncSession = Depends(get_db)):
    settings = await db.scalar(select(SettingsModel).limit(1))
    if not settings:
        settings = SettingsModel()
        db.add(settings)
        await db.flush()
    return templates.TemplateResponse(
        "settings/index.html",
        {"request": request, "settings": settings},
    )


@router.post("/")
async def update_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    org_name: str = Form(...),
    siret: str = Form(""),
    vat_number: str = Form(""),
):
    settings = await db.scalar(select(SettingsModel).limit(1))
    if not settings:
        settings = SettingsModel()
        db.add(settings)
    settings.org_name = org_name
    settings.siret = siret
    settings.vat_number = vat_number
    await db.flush()
    return RedirectResponse("/settings", status_code=302)


@router.get("/activities")
async def activities_form(request: Request, db: AsyncSession = Depends(get_db)):
    activities = (await db.scalars(select(Activity))).all()
    return templates.TemplateResponse(
        "settings/activities.html",
        {"request": request, "activities": activities},
    )


@router.post("/activities")
async def create_activity(
    request: Request,
    db: AsyncSession = Depends(get_db),
    code: str = Form(...),
    name: str = Form(...),
    color: str = Form("#1d4ed8"),
    vat_rate_default: float = Form(0.0),
    invoice_prefix: str = Form(...),
    revenue_account: str = Form("706000"),
):
    activity = Activity(
        code=code,
        name=name,
        color=color,
        vat_rate_default=vat_rate_default,
        invoice_prefix=invoice_prefix,
        revenue_account=revenue_account,
    )
    db.add(activity)
    await db.flush()
    return RedirectResponse("/settings/activities", status_code=302)


@router.get("/services")
async def services_form(request: Request, db: AsyncSession = Depends(get_db), activity_id: Optional[int] = None):
    activities = (await db.scalars(select(Activity))).all()
    query = select(Service)
    if activity_id:
        query = query.where(Service.activity_id == activity_id)
    services = (await db.scalars(query)).all()
    return templates.TemplateResponse(
        "settings/services.html",
        {"request": request, "activities": activities, "services": services},
    )


@router.post("/services")
async def create_service(
    db: AsyncSession = Depends(get_db),
    activity_id: int = Form(...),
    code: str = Form(...),
    name: str = Form(...),
    price_ht: float = Form(...),
    vat_rate: float = Form(...),
    default_duration_min: int = Form(60),
    description: str = Form(""),
):
    service = Service(
        activity_id=activity_id,
        code=code,
        name=name,
        price_ht=price_ht,
        vat_rate=vat_rate,
        default_duration_min=default_duration_min,
        description=description,
    )
    db.add(service)
    await db.flush()
    return RedirectResponse("/settings/services", status_code=302)

