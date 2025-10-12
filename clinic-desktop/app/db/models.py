from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, nullable=False)


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_name: Mapped[str | None] = mapped_column(String(255))
    siret: Mapped[str | None] = mapped_column(String(14))
    vat_number: Mapped[str | None] = mapped_column(String(32))
    address_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    iban_bic: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    logo_path: Mapped[str | None] = mapped_column(String(255))
    legal_footer_text: Mapped[str | None] = mapped_column(Text)
    fiscal_year_start_month: Mapped[int | None] = mapped_column(Integer, default=1)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16))
    default_vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    invoice_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    next_seq: Mapped[int] = mapped_column(Integer, default=1)
    revenue_account: Mapped[str | None] = mapped_column(String(32))
    pdf_header_html: Mapped[str | None] = mapped_column(Text)
    pdf_footer_html: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    services: Mapped[list["Service"]] = relationship(back_populates="activity")


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_duration_min: Mapped[int | None] = mapped_column(Integer)
    price_ht: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    activity: Mapped[Activity] = relationship(back_populates="services")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    birthdate: Mapped[dt.date | None] = mapped_column(Date)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    address_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    tags_json: Mapped[list[str] | None] = mapped_column(JSON)
    notes_encrypted: Mapped[str | None] = mapped_column(Text)
    consent_rgpd: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    start_dt: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    end_dt: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    title: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="confirmed")


class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
    notes_internal: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft")


class ConsultationItem(Base):
    __tablename__ = "consultation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"), nullable=False)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    price_ht: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    label_override: Mapped[str | None] = mapped_column(String(255))


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
    number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    total_ht: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_ttc: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    public_note: Mapped[str | None] = mapped_column(Text)
    private_note: Mapped[str | None] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(String(255))


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255))
    qty: Mapped[float] = mapped_column(Float, default=1.0)
    price_ht: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_ht: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_ttc: Mapped[float] = mapped_column(Float, default=0.0)
    service_id_nullable: Mapped[int | None] = mapped_column(ForeignKey("services.id"))


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
    method: Mapped[str] = mapped_column(String(32))
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    reference: Mapped[str | None] = mapped_column(String(64))


class CreditNote(Base):
    __tablename__ = "credit_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
    total_ht: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_ttc: Mapped[float] = mapped_column(Float, default=0.0)
    pdf_path: Mapped[str | None] = mapped_column(String(255))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    meta_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


__all__ = [
    "User",
    "Settings",
    "Activity",
    "Service",
    "Patient",
    "Appointment",
    "Consultation",
    "ConsultationItem",
    "Invoice",
    "InvoiceItem",
    "Payment",
    "CreditNote",
    "AuditLog",
]
