from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .billing import LineItem, billing_calculator

try:  # pragma: no cover - dépendance optionnelle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    HAS_REPORTLAB = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_REPORTLAB = False


@dataclass
class InvoiceDocument:
    activity_name: str
    activity_code: str
    invoice_number: str
    invoice_date: dt.date
    patient_name: str
    lines: List[LineItem]
    notes: str = ""


def _generate_with_reportlab(doc: InvoiceDocument, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = SimpleDocTemplate(str(path), pagesize=A4)
    styles = getSampleStyleSheet()
    story: list = []

    story.append(Paragraph(f"<b>{doc.activity_name}</b>", styles["Title"]))
    story.append(Paragraph(f"Facture {doc.invoice_number}", styles["Heading2"]))
    story.append(Paragraph(f"Date : {doc.invoice_date.isoformat()}", styles["Normal"]))
    story.append(Paragraph(f"Patient : {doc.patient_name}", styles["Normal"]))
    story.append(Spacer(1, 12))

    data = [["Prestation", "Qté", "PU HT", "TVA", "Total TTC"]]
    totals = billing_calculator.compute(doc.lines)
    for line in doc.lines:
        data.append(
            [
                line.label,
                f"{line.qty}",
                f"{line.price_ht:.2f}",
                f"{(line.vat_rate * 100):.0f}%",
                f"{line.total_ttc():.2f}",
            ]
        )

    table = Table(data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"Total HT : {totals.total_ht:.2f} €", styles["Normal"]))
    story.append(Paragraph(f"Total TVA : {totals.total_vat:.2f} €", styles["Normal"]))
    story.append(Paragraph(f"Total TTC : {totals.total_ttc:.2f} €", styles["Heading3"]))

    if doc.notes:
        story.append(Spacer(1, 12))
        story.append(Paragraph(doc.notes, styles["Italic"]))

    pdf.build(story)
    return path


def _generate_minimal_pdf(doc: InvoiceDocument, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    totals = billing_calculator.compute(doc.lines)
    lines_text = "\n".join(
        f"- {line.label}: {line.qty} x {line.price_ht:.2f} HT TVA {line.vat_rate * 100:.0f}% = {line.total_ttc():.2f} EUR"
        for line in doc.lines
    )
    content = (
        f"Invoice: {doc.invoice_number}\n"
        f"Date: {doc.invoice_date.isoformat()}\n"
        f"Patient: {doc.patient_name}\n"
        f"{lines_text}\n"
        f"Total HT: {totals.total_ht:.2f} EUR\n"
        f"Total TVA: {totals.total_vat:.2f} EUR\n"
        f"Total TTC: {totals.total_ttc:.2f} EUR\n"
        f"{doc.notes}"
    )
    escaped = content.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\n", "\\n")
    padding = " " * 800
    stream_content = f"BT /F1 12 Tf 50 780 Td ({escaped}) Tj ET{padding}"

    objects = [
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n",
        "2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n",
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n",
        f"4 0 obj<</Length {len(stream_content)}>>stream\n{stream_content}\nendstream endobj\n",
        "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n",
    ]

    parts = ["%PDF-1.4\n"]
    offsets = [0]
    current_offset = len(parts[0])
    for obj in objects:
        offsets.append(current_offset)
        parts.append(obj)
        current_offset += len(obj)

    xref_lines = [f"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref_lines.append(f"{offset:010} 00000 n \n")
    xref = f"xref\n0 {len(objects) + 1}\n" + "".join(xref_lines)
    trailer = f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{current_offset}\n%%EOF"

    path.write_bytes("".join(parts + [xref, trailer]).encode("latin-1"))
    return path


def generate_invoice_pdf(doc: InvoiceDocument, path: Path) -> Path:
    if HAS_REPORTLAB:
        return _generate_with_reportlab(doc, path)
    return _generate_minimal_pdf(doc, path)


__all__ = ["generate_invoice_pdf", "InvoiceDocument"]
