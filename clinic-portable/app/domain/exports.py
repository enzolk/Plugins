from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Iterable, List

from openpyxl import Workbook


@dataclass
class JournalRow:
    date: date
    invoice_number: str
    patient: str
    base_ht: float
    vat_amount: float
    total_ttc: float
    revenue_account: str
    payment_method: str

    def to_row(self) -> List[str]:
        return [
            self.date.isoformat(),
            self.invoice_number,
            self.patient,
            f"{self.base_ht:.2f}",
            f"{self.vat_amount:.2f}",
            f"{self.total_ttc:.2f}",
            self.revenue_account,
            self.payment_method,
        ]


HEADERS = [
    "Date",
    "N° facture",
    "Patient",
    "Base HT",
    "TVA",
    "Total TTC",
    "Compte produits",
    "Mode de paiement",
]


def export_journal_csv(rows: Iterable[JournalRow], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(HEADERS)
        for row in rows:
            writer.writerow(row.to_row())
    return output_path


def export_journal_xlsx(rows: Iterable[JournalRow], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Journal des ventes"
    ws.append(HEADERS)
    for row in rows:
        ws.append(row.to_row())
    for column_cells in ws.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        column_letter = column_cells[0].column_letter
        ws.column_dimensions[column_letter].width = max_length + 2
    wb.save(output_path)
    return output_path


__all__ = ["JournalRow", "export_journal_csv", "export_journal_xlsx"]
