import enum
from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    practitioner = "praticien"
    assistant = "assistant"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.assistant)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class Activity(Base, TimestampMixin):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#1d4ed8")
    vat_rate_default: Mapped[float] = mapped_column(Float, default=0.0)
    invoice_prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    next_seq: Mapped[int] = mapped_column(Integer, default=1)
    revenue_account: Mapped[str] = mapped_column(String(20), default="706000")
    pdf_header_html: Mapped[str] = mapped_column(Text, default="")
    pdf_footer_html: Mapped[str] = mapped_column(Text, default="")

    services: Mapped[list["Service"]] = relationship(back_populates="activity")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="activity")


class Service(Base, TimestampMixin):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    default_duration_min: Mapped[int] = mapped_column(Integer, default=60)
    price_ht: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    activity: Mapped[Activity] = relationship(back_populates="services")


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("first_name", "last_name", "birthdate", name="uq_patient_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    birthdate: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes_encrypted: Mapped[str] = mapped_column(Text, default="")
    consent_rgpd: Mapped[bool] = mapped_column(Boolean, default=False)

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient")
    consultations: Mapped[list["Consultation"]] = relationship(back_populates="patient")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="patient")


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    start_dt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_dt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="confirmé")

    patient: Mapped[Patient] = relationship(back_populates="appointments")
    activity: Mapped[Activity] = relationship()


class Consultation(Base, TimestampMixin):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    notes_internal: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="à facturer")

    patient: Mapped[Patient] = relationship(back_populates="consultations")
    activity: Mapped[Activity] = relationship()
    items: Mapped[list["ConsultationItem"]] = relationship(
        back_populates="consultation", cascade="all, delete-orphan"
    )


class ConsultationItem(Base):
    __tablename__ = "consultation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    price_ht: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    label_override: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    consultation: Mapped[Consultation] = relationship(back_populates="items")
    service: Mapped[Service] = relationship()


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="brouillon")
    total_ht: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_ttc: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    notes_public: Mapped[str] = mapped_column(Text, default="")
    notes_private: Mapped[str] = mapped_column(Text, default="")
    pdf_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    activity: Mapped[Activity] = relationship(back_populates="invoices")
    patient: Mapped[Patient] = relationship(back_populates="invoices")
    credit_notes: Mapped[list["CreditNote"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    price_ht: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_ht: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_ttc: Mapped[float] = mapped_column(Float, default=0.0)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("services.id"), nullable=True)

    invoice: Mapped[Invoice] = relationship(back_populates="items")
    service: Mapped[Optional[Service]] = relationship()


class PaymentMethod(str, enum.Enum):
    cash = "espèces"
    cheque = "chèque"
    card = "carte"
    transfer = "virement"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    invoice: Mapped[Invoice] = relationship(back_populates="payments")


class CreditNote(Base, TimestampMixin):
    __tablename__ = "credit_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    total_ht: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_ttc: Mapped[float] = mapped_column(Float, default=0.0)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    invoice: Mapped[Invoice] = relationship(back_populates="credit_notes")


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    org_name: Mapped[str] = mapped_column(String(200), default="Cabinet local")
    siret: Mapped[str] = mapped_column(String(50), default="")
    vat_number: Mapped[str] = mapped_column(String(50), default="")
    address_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    iban_bic: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    logo_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), default="fr")
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, default=1)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    meta_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    user: Mapped[Optional[User]] = relationship(back_populates="audit_logs")
