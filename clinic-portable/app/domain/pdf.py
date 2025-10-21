from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from weasyprint import HTML


def load_template_fragment(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def build_invoice_html(data: Dict, header: str, footer: str) -> str:
    items_html = "".join(
        f"""
        <tr>
            <td>{item['label']}</td>
            <td class='qty'>{item['qty']}</td>
            <td class='price'>{item['price_ht']:.2f} €</td>
            <td class='price'>{item['vat_rate']}%</td>
            <td class='price'>{item['total_ht']:.2f} €</td>
            <td class='price'>{item['total_vat']:.2f} €</td>
            <td class='price'>{item['total_ttc']:.2f} €</td>
        </tr>
        """
        for item in data["items"]
    )

    payments_html = "".join(
        f"<li>{payment['date']} – {payment['method']} : {payment['amount']:.2f} €</li>"
        for payment in data.get("payments", [])
    )

    return f"""
    <html>
    <head>
        <meta charset='utf-8'/>
        <style>
            body {{ font-family: 'DejaVu Sans', Arial, sans-serif; margin: 2cm; }}
            header {{ margin-bottom: 20px; }}
            footer {{ margin-top: 30px; font-size: 10pt; color: #555; }}
            h1 {{ font-size: 24pt; margin: 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ border-bottom: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f5f5f5; }}
            td.qty {{ text-align: center; }}
            td.price {{ text-align: right; }}
            ul {{ padding-left: 16px; }}
            .totals {{ margin-top: 20px; text-align: right; font-size: 12pt; }}
        </style>
    </head>
    <body>
        <header>{header}</header>
        <h1>Facture {data['invoice_number']}</h1>
        <p><strong>Date :</strong> {data['date']}</p>
        <p><strong>Patient :</strong> {data['patient']['display_name']}<br/>
           {data['patient']['address']}</p>
        <table>
            <thead>
                <tr>
                    <th>Description</th>
                    <th>Qté</th>
                    <th>PU HT</th>
                    <th>TVA</th>
                    <th>Total HT</th>
                    <th>TVA</th>
                    <th>Total TTC</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>
        <div class='totals'>
            <p>Total HT : {data['totals']['total_ht']:.2f} €</p>
            <p>Total TVA : {data['totals']['total_vat']:.2f} €</p>
            <p><strong>Total TTC : {data['totals']['total_ttc']:.2f} €</strong></p>
        </div>
        <section>
            <h2>Paiements</h2>
            <ul>{payments_html or '<li>Aucun paiement enregistré</li>'}</ul>
        </section>
        <footer>{footer}</footer>
    </body>
    </html>
    """


def generate_invoice_pdf(data: Dict, templates_dir: Path, output_path: Path) -> Path:
    header = load_template_fragment(templates_dir / data["activity_code"] / "header.html")
    footer = load_template_fragment(templates_dir / data["activity_code"] / "footer.html")
    if not header:
        header = load_template_fragment(templates_dir / f"invoice_header_{data['activity_code']}.html")
    if not footer:
        footer = load_template_fragment(templates_dir / f"invoice_footer_{data['activity_code']}.html")

    html = build_invoice_html(data, header, footer)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(templates_dir)).write_pdf(str(output_path))
    return output_path


__all__ = ["generate_invoice_pdf"]
