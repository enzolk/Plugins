from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from ..config import get_settings
from ..models import Activity, Invoice, InvoiceItem, Patient, Settings

_env = Environment(
    loader=FileSystemLoader(str(get_settings().template_path)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_invoice_pdf(
    invoice: Invoice,
    patient: Patient,
    activity: Activity,
    settings: Settings | None,
    lines: list[InvoiceItem],
) -> Path:
    settings_obj = settings or Settings()
    base_path = get_settings().files_path / "invoices" / str(invoice.date.year)
    base_path.mkdir(parents=True, exist_ok=True)
    template = _env.get_template("invoices/pdf.html")
    html = template.render(
        invoice=invoice,
        patient=patient,
        activity=activity,
        settings=settings_obj,
        items=lines,
    )
    target = base_path / f"{invoice.number}.pdf"
    HTML(string=html, base_url=str(get_settings().base_path)).write_pdf(target)
    invoice.pdf_path = str(target.relative_to(get_settings().base_path))
    return target

