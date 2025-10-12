from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Activity


async def next_invoice_number(session: AsyncSession, activity_id: int, invoice_date: date) -> str:
    activity = await session.scalar(select(Activity).where(Activity.id == activity_id))
    if not activity:
        raise ValueError("Activité introuvable")

    prefix = activity.invoice_prefix
    year = invoice_date.year
    seq = activity.next_seq or 1
    number = f"{prefix}{year}-{seq:04d}"
    activity.next_seq = seq + 1
    await session.flush()
    return number

