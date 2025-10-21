from datetime import date

from app.domain.exports import JournalRow, export_journal_csv, export_journal_xlsx


def sample_rows():
    return [
        JournalRow(
            date=date(2024, 1, 10),
            invoice_number="OST-2024-0001",
            patient="Alice Martin",
            base_ht=50.0,
            vat_amount=0.0,
            total_ttc=50.0,
            revenue_account="7061",
            payment_method="Carte",
        )
    ]


def test_export_csv(tmp_path):
    path = tmp_path / "journal.csv"
    export_journal_csv(sample_rows(), path)
    content = path.read_text(encoding="utf-8")
    assert "OST-2024-0001" in content


def test_export_xlsx(tmp_path):
    path = tmp_path / "journal.xlsx"
    export_journal_xlsx(sample_rows(), path)
    assert path.exists() and path.stat().st_size > 0
