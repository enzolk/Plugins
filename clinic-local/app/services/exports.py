import csv
from datetime import date
from pathlib import Path
from typing import List, Optional

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Activity, Invoice, InvoiceItem, Patient


async def sales_rows(
    session: AsyncSession,
    activity_code: Optional[str],
    start: date,
    end: date,
) -> List[dict]:
    query = (
        select(
            Invoice.date,
            Invoice.number,
            (Patient.last_name + " " + Patient.first_name).label("patient"),
            func.sum(InvoiceItem.total_ht).label("ht"),
            func.sum(InvoiceItem.total_vat).label("vat"),
            func.sum(InvoiceItem.total_ttc).label("ttc"),
            Activity.revenue_account,
        )
        .join(Patient, Patient.id == Invoice.patient_id)
        .join(Activity, Activity.id == Invoice.activity_id)
        .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .where(Invoice.date.between(start, end))
        .group_by(Invoice.id, Patient.last_name, Patient.first_name, Activity.revenue_account)
        .order_by(Invoice.date)
    )
    if activity_code:
        query = query.where(Activity.code == activity_code)

    result = await session.execute(query)
    rows = []
    for row in result:
        rows.append(
            {
                "date": row.date,
                "number": row.number,
                "patient": row.patient,
                "ht": float(row.ht or 0),
                "vat": float(row.vat or 0),
                "ttc": float(row.ttc or 0),
                "account": row.revenue_account,
            }
        )
    return rows


async def export_sales(
    session: AsyncSession,
    activity_code: Optional[str],
    start: date,
    end: date,
    fmt: str = "csv",
) -> Path:
    rows = await sales_rows(session, activity_code, start, end)
    exports_dir = get_settings().exports_path
    exports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"ventes-{activity_code or 'all'}-{start}-{end}.{fmt}"
    target = exports_dir / filename

    if fmt == "csv":
        with target.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "N°", "Patient", "Base HT", "TVA", "Total TTC", "Compte"])
            for row in rows:
                writer.writerow(
                    [row["date"], row["number"], row["patient"], row["ht"], row["vat"], row["ttc"], row["account"]]
                )
    elif fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.append(["Date", "N°", "Patient", "Base HT", "TVA", "Total TTC", "Compte"])
        for row in rows:
            ws.append([row["date"], row["number"], row["patient"], row["ht"], row["vat"], row["ttc"], row["account"]])
        wb.save(target)
    else:
        raise ValueError("Format non supporté")

    return target

