from __future__ import annotations

from ..app_context import app_ctx
from ..db import models


def load_demo_data() -> None:
    with app_ctx.session() as session:
        if session.query(models.Activity).count():
            return
        ost = models.Activity(
            code="OST",
            name="Ostéopathie",
            color="#0a84ff",
            default_vat_rate=0.0,
            invoice_prefix="OST-",
            next_seq=1,
            revenue_account="706OST",
            pdf_header_html="<h1>Cabinet Ostéopathie</h1>",
            pdf_footer_html="Merci pour votre confiance.",
        )
        drl = models.Activity(
            code="DRL",
            name="Drainage lymphatique",
            color="#43a047",
            default_vat_rate=0.2,
            invoice_prefix="DRL-",
            next_seq=1,
            revenue_account="706DRL",
            pdf_header_html="<h1>Drainage Lymphatique</h1>",
            pdf_footer_html="Soin réalisé avec bienveillance.",
        )
        session.add_all([ost, drl])
        session.flush()

        services = [
            models.Service(
                activity_id=ost.id,
                code="OST30",
                name="Séance ostéo 30 min",
                default_duration_min=30,
                price_ht=60.0,
                vat_rate=0.0,
            ),
            models.Service(
                activity_id=ost.id,
                code="OST45",
                name="Séance ostéo 45 min",
                default_duration_min=45,
                price_ht=80.0,
                vat_rate=0.0,
            ),
            models.Service(
                activity_id=drl.id,
                code="DRL30",
                name="Drainage 30 min",
                default_duration_min=30,
                price_ht=50.0,
                vat_rate=0.2,
            ),
        ]
        session.add_all(services)
        session.commit()


if __name__ == "__main__":
    load_demo_data()
