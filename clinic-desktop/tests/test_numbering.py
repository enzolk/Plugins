from __future__ import annotations

import datetime as dt

from app.domain.numbering import numbering_service
from app.app_context import app_ctx
from app.db import models


def test_numbering_sequences_independent():
    today = dt.date(2025, 1, 1)
    number_ost = numbering_service.next_invoice_number("OST", date=today)
    number_drl = numbering_service.next_invoice_number("DRL", date=today)
    assert number_ost.startswith("OST-2025-")
    assert number_drl.startswith("DRL-2025-")
    assert number_ost != number_drl


def test_numbering_reset_on_new_year():
    end_year = dt.date(2024, 12, 31)
    start_year = dt.date(2025, 1, 2)
    numbering_service.next_invoice_number("OST", date=end_year)
    number_new_year = numbering_service.next_invoice_number("OST", date=start_year)
    assert number_new_year.endswith("0001")
