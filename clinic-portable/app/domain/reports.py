from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Invoice, InvoiceItem, Payment


def compute_dashboard(session: Session, activity_id: int, start: date, end: date) -> Dict:
    invoices = (
        session.query(Invoice)
        .filter(Invoice.activity_id == activity_id, Invoice.date >= start, Invoice.date <= end)
        .all()
    )
    total_ht = sum(invoice.total_ht for invoice in invoices)
    total_vat = sum(invoice.total_vat for invoice in invoices)
    total_ttc = sum(invoice.total_ttc for invoice in invoices)

    payments = (
        session.query(Payment)
        .join(Invoice)
        .filter(Invoice.activity_id == activity_id, Payment.date >= start, Payment.date <= end)
        .all()
    )
    total_paid = sum(payment.amount for payment in payments)
    outstanding = total_ttc - total_paid

    nb_consults = session.query(func.count(Invoice.id)).filter(
        Invoice.activity_id == activity_id, Invoice.date >= start, Invoice.date <= end
    ).scalar()

    avg_basket = total_ttc / nb_consults if nb_consults else 0

    return {
        "totals": {
            "ht": total_ht,
            "vat": total_vat,
            "ttc": total_ttc,
            "paid": total_paid,
            "outstanding": outstanding,
        },
        "counts": {
            "invoices": nb_consults,
            "avg_basket": avg_basket,
        },
        "top_services": top_services(session, activity_id, start, end),
        "monthly": monthly_series(session, activity_id, start.year),
    }


def top_services(session: Session, activity_id: int, start: date, end: date, limit: int = 5) -> List[Dict]:
    query = (
        session.query(
            InvoiceItem.label,
            func.sum(InvoiceItem.total_ttc).label("total"),
            func.sum(InvoiceItem.qty).label("qty"),
        )
        .join(Invoice)
        .filter(
            Invoice.activity_id == activity_id,
            Invoice.date >= start,
            Invoice.date <= end,
        )
        .group_by(InvoiceItem.label)
        .order_by(func.sum(InvoiceItem.total_ttc).desc())
        .limit(limit)
    )
    return [
        {"label": row[0], "total": row[1], "qty": row[2]}
        for row in query
    ]


def monthly_series(session: Session, activity_id: int, year: int) -> List[Dict]:
    results = defaultdict(lambda: {"ht": 0.0, "ttc": 0.0, "vat": 0.0})
    invoices = (
        session.query(Invoice)
        .filter(
            Invoice.activity_id == activity_id,
            func.strftime("%Y", Invoice.date) == str(year),
        )
        .all()
    )
    for invoice in invoices:
        month = int(invoice.date.strftime("%m"))
        results[month]["ht"] += invoice.total_ht
        results[month]["vat"] += invoice.total_vat
        results[month]["ttc"] += invoice.total_ttc
    series = []
    for month in range(1, 13):
        values = results[month]
        series.append({"month": month, **values})
    return series


__all__ = ["compute_dashboard", "top_services", "monthly_series"]
