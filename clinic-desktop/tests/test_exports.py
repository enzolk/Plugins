from __future__ import annotations

import csv
import datetime as dt

from app.domain.exports import ExportRow, export_sales_csv, export_sales_xlsx


def sample_rows():
    return [
        ExportRow(
            date=dt.date(2024, 1, 10),
            invoice_number="OST-2024-0001",
            patient="Dupont Alice",
            base_ht=60.0,
            vat=0.0,
            total_ttc=60.0,
            revenue_account="706OST",
            payment_method="CB",
        ),
        ExportRow(
            date=dt.date(2024, 1, 12),
            invoice_number="DRL-2024-0001",
            patient="Martin Bob",
            base_ht=50.0,
            vat=10.0,
            total_ttc=60.0,
            revenue_account="706DRL",
            payment_method="Chèque",
        ),
    ]


def test_export_sales_csv(tmp_path):
    path = tmp_path / "journal.csv"
    export_sales_csv(sample_rows(), path)
    with path.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter=";"))
    assert rows[0][0] == "Date"
    assert rows[1][1] == "OST-2024-0001"
    assert rows[2][6] == "706DRL"


def test_export_sales_xlsx(tmp_path):
    path = tmp_path / "journal.xlsx"
    export_sales_xlsx(sample_rows(), path)
    assert path.exists()
    assert path.stat().st_size > 0
