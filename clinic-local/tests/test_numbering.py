import pytest
from datetime import date
from sqlalchemy import select

from app.models import Activity
from app.services.numbering import next_invoice_number


@pytest.mark.asyncio
async def test_next_invoice_number(async_session):
    activity = Activity(code="OST", name="Ostéopathie", invoice_prefix="OST-", color="#1d4ed8")
    async_session.add(activity)
    await async_session.flush()

    number1 = await next_invoice_number(async_session, activity.id, date(2024, 1, 1))
    number2 = await next_invoice_number(async_session, activity.id, date(2024, 1, 2))

    assert number1 == "OST-2024-0001"
    assert number2 == "OST-2024-0002"

