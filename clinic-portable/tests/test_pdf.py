from datetime import date
from pathlib import Path

import pytest

weasyprint = pytest.importorskip("weasyprint")

from app.domain.pdf import generate_invoice_pdf

def test_generate_invoice_pdf(tmp_path):
    templates_dir = Path("files/pdf_templates")
    output = tmp_path / "invoice.pdf"

    data = {
        "invoice_number": "OST-2024-0001",
        "date": date(2024, 1, 10).isoformat(),
        "activity_code": "OST",
        "patient": {
            "display_name": "Alice Martin",
            "address": "1 Rue Demo 75001 Paris",
        },
        "items": [
            {
                "label": "Consultation",
                "qty": 1,
                "price_ht": 50.0,
                "vat_rate": 0,
                "total_ht": 50.0,
                "total_vat": 0.0,
                "total_ttc": 50.0,
            }
        ],
        "payments": [
            {"date": "2024-01-10", "method": "Carte", "amount": 50.0}
        ],
        "totals": {
            "total_ht": 50.0,
            "total_vat": 0.0,
            "total_ttc": 50.0,
        },
    }

    pdf_path = generate_invoice_pdf(data, templates_dir, output)
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
