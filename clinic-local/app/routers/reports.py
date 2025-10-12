from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db
from ..templating import templates
from ..models import Activity, Invoice

router = APIRouter()


@router.get("/")
async def reports_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    start: date = Query(default=date(date.today().year, 1, 1)),
    end: date = Query(default=date.today()),
):
    query = (
        select(
            Activity.code,
            func.sum(Invoice.total_ht),
            func.sum(Invoice.total_vat),
            func.sum(Invoice.total_ttc),
        )
        .join(Activity, Activity.id == Invoice.activity_id)
        .where(Invoice.date.between(start, end))
        .group_by(Activity.code)
    )
    result = await db.execute(query)
    data = [
        {
            "code": row[0],
            "total_ht": float(row[1] or 0),
            "total_vat": float(row[2] or 0),
            "total_ttc": float(row[3] or 0),
        }
        for row in result
    ]
    return templates.TemplateResponse(
        "reports/index.html",
        {"request": request, "data": data, "start": start, "end": end},
    )

