from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook


@dataclass
class ExportRow:
    date: dt.date
    invoice_number: str
    patient: str
    base_ht: float
    vat: float
    total_ttc: float
    revenue_account: str
    payment_method: str


def export_sales_csv(rows: Iterable[ExportRow], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")
        writer.writerow([
            "Date",
            "Facture",
            "Patient",
            "Base HT",
            "TVA",
            "Total TTC",
            "Compte produit",
            "Paiement",
        ])
        for row in rows:
            writer.writerow([
                row.date.isoformat(),
                row.invoice_number,
                row.patient,
                f"{row.base_ht:.2f}",
                f"{row.vat:.2f}",
                f"{row.total_ttc:.2f}",
                row.revenue_account,
                row.payment_method,
            ])
    return path


def export_sales_xlsx(rows: Iterable[ExportRow], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Journal ventes"
    ws.append([
        "Date",
        "Facture",
        "Patient",
        "Base HT",
        "TVA",
        "Total TTC",
        "Compte produit",
        "Paiement",
    ])
    for row in rows:
        ws.append([
            row.date.isoformat(),
            row.invoice_number,
            row.patient,
            float(f"{row.base_ht:.2f}"),
            float(f"{row.vat:.2f}"),
            float(f"{row.total_ttc:.2f}"),
            row.revenue_account,
            row.payment_method,
        ])
    wb.save(path)
    return path


__all__ = ["ExportRow", "export_sales_csv", "export_sales_xlsx"]
