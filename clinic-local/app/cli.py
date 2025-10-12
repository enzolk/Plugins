import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from sqlalchemy import select

from .db import AsyncSessionFactory
from .models import (
    Activity,
    Consultation,
    ConsultationItem,
    Invoice,
    InvoiceItem,
    Patient,
    Payment,
    PaymentMethod,
    Service,
    Settings,
    User,
    UserRole,
)
from .security import hash_password
from .services import backups, exports

app = typer.Typer(help="Outils de gestion du cabinet")


async def _seed_demo(session):
    existing = await session.scalar(select(User).limit(1))
    if existing:
        return False

    settings = Settings(org_name="Cabinet Démo", siret="12345678900011")
    session.add(settings)

    ost = Activity(
        code="OST",
        name="Ostéopathie",
        color="#1d4ed8",
        vat_rate_default=0.0,
        invoice_prefix="OST-",
        revenue_account="706100",
    )
    drl = Activity(
        code="DRL",
        name="Drainage lymphatique",
        color="#16a34a",
        vat_rate_default=20.0,
        invoice_prefix="DRL-",
        revenue_account="706200",
    )
    session.add_all([ost, drl])
    await session.flush()

    services = [
        Service(activity_id=ost.id, code="OST_CONSULT", name="Consultation ostéo", price_ht=60.0, vat_rate=0.0),
        Service(activity_id=ost.id, code="OST_REVIEW", name="Suivi ostéo", price_ht=50.0, vat_rate=0.0),
        Service(activity_id=drl.id, code="DRL_SESSION", name="Séance drainage", price_ht=70.0, vat_rate=20.0),
        Service(activity_id=drl.id, code="DRL_PACK", name="Forfait drainage", price_ht=180.0, vat_rate=20.0),
    ]
    session.add_all(services)
    await session.flush()

    patients = [
        Patient(first_name="Alice", last_name="Martin", email="alice@example.com", phone="0600000001"),
        Patient(first_name="Bruno", last_name="Durand", email="bruno@example.com", phone="0600000002"),
        Patient(first_name="Claire", last_name="Petit", email="claire@example.com", phone="0600000003"),
        Patient(first_name="David", last_name="Moreau", email="david@example.com", phone="0600000004"),
    ]
    session.add_all(patients)
    await session.flush()

    users = [
        User(email="admin@example.com", password_hash=hash_password("admin123"), role=UserRole.admin),
        User(email="praticien@example.com", password_hash=hash_password("demo123"), role=UserRole.practitioner),
        User(email="assistant@example.com", password_hash=hash_password("demo123"), role=UserRole.assistant),
    ]
    session.add_all(users)

    for idx, patient in enumerate(patients):
        activity = ost if idx % 2 == 0 else drl
        service = services[0] if activity.id == ost.id else services[2]
        consultation = Consultation(
            activity_id=activity.id,
            patient_id=patient.id,
            date=date.today() - timedelta(days=idx * 7),
            status="facturé",
        )
        consultation.items.append(
            ConsultationItem(
                service_id=service.id,
                qty=1,
                price_ht=service.price_ht,
                vat_rate=service.vat_rate,
            )
        )
        session.add(consultation)
        await session.flush()
        invoice = Invoice(
            activity_id=activity.id,
            patient_id=patient.id,
            date=consultation.date,
            number=f"{activity.invoice_prefix}{consultation.date.year}-{idx+1:04d}",
            status="payé",
            total_ht=service.price_ht,
            total_vat=service.price_ht * service.vat_rate / 100,
            total_ttc=service.price_ht * (1 + service.vat_rate / 100),
        )
        invoice.items.append(
            InvoiceItem(
                label=service.name,
                qty=1,
                price_ht=service.price_ht,
                vat_rate=service.vat_rate,
                total_ht=service.price_ht,
                total_vat=service.price_ht * service.vat_rate / 100,
                total_ttc=service.price_ht * (1 + service.vat_rate / 100),
                service_id=service.id,
            )
        )
        session.add(invoice)
        await session.flush()
        session.add(
            Payment(
                invoice_id=invoice.id,
                amount=invoice.total_ttc,
                method=PaymentMethod.card,
                date=invoice.date,
            )
        )
    return True


@app.command()
def seed(if_empty: bool = typer.Option(False, help="Ne rien faire si des utilisateurs existent")):
    """Charge les données de démonstration."""

    async def runner():
        async with AsyncSessionFactory() as session:
            if if_empty:
                existing = await session.scalar(select(User).limit(1))
                if existing:
                    typer.echo("Base déjà initialisée")
                    return
            await _seed_demo(session)
            await session.commit()
            typer.echo("Données de démonstration installées")

    asyncio.run(runner())


@app.command()
def backup(output: Optional[Path] = typer.Option(None, help="Chemin de destination")):
    path = backups.backup(output)
    typer.echo(f"Sauvegarde créée: {path}")


@app.command()
def restore(archive: Path):
    backups.restore(archive)
    typer.echo("Restauration terminée")


@app.command()
def export_sales(activity: Optional[str] = typer.Option(None), from_date: date = typer.Option(...), to_date: date = typer.Option(...), format: str = typer.Option("csv")):
    async def runner():
        async with AsyncSessionFactory() as session:
            path = await exports.export_sales(session, activity, from_date, to_date, format)
            await session.commit()
            typer.echo(f"Export généré: {path}")

    asyncio.run(runner())


@app.command()
def reset_password(email: str, password: str):
    async def runner():
        async with AsyncSessionFactory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            if not user:
                typer.echo("Utilisateur introuvable")
                return
            user.password_hash = hash_password(password)
            await session.commit()
            typer.echo("Mot de passe mis à jour")

    asyncio.run(runner())


if __name__ == "__main__":
    app()

