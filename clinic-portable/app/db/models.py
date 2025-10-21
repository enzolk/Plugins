from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    org_name: Mapped[Optional[str]] = mapped_column(String(255))
    siret: Mapped[Optional[str]] = mapped_column(String(20))
    vat_number: Mapped[Optional[str]] = mapped_column(String(32))
    address_json: Mapped[Optional[str]] = mapped_column(Text)
    iban_bic: Mapped[Optional[str]] = mapped_column(String(128))
    logo_path: Mapped[Optional[str]] = mapped_column(String(255))
    legal_footer_text: Mapped[Optional[str]] = mapped_column(Text)
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, default=1)

    def address(self) -> Dict[str, Any]:
        return json.loads(self.address_json or "{}")


class Activity(Base, TimestampMixin):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#2F80ED")
    default_vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    invoice_prefix: Mapped[str] = mapped_column(String(16), default="ACT-")
    next_seq: Mapped[int] = mapped_column(Integer, default=1)
    revenue_account: Mapped[str] = mapped_column(String(32), default="706")
    pdf_header_html: Mapped[Optional[str]] = mapped_column(Text)
    pdf_footer_html: Mapped[Optional[str]] = mapped_column(Text)

    services: Mapped[List["Service"]] = relationship("Service", back_populates="activity")
    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="activity")


class Service(Base, TimestampMixin):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_duration_min: Mapped[int] = mapped_column(Integer, default=30)
    price_ht: Mapped[float] = mapped_column(Float, nullable=False)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    activity: Mapped[Activity] = relationship("Activity", back_populates="services")


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    birthdate: Mapped[Optional[date]] = mapped_column(Date)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(64))
    address_json: Mapped[Optional[str]] = mapped_column(Text)
    tags_json: Mapped[Optional[str]] = mapped_column(Text)
    notes_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    consent_rgpd: Mapped[bool] = mapped_column(Boolean, default=False)

    consultations: Mapped[List["Consultation"]] = relationship(
        "Consultation", back_populates="patient", cascade="all, delete-orphan"
    )
    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="patient")

    def tags(self) -> List[str]:
        if not self.tags_json:
            return []
        try:
            return json.loads(self.tags_json)
        except json.JSONDecodeError:
            return []

    def address(self) -> Dict[str, Any]:
        return json.loads(self.address_json or "{}")


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    start_dt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_dt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="planned")

    activity: Mapped[Activity] = relationship("Activity")
    patient: Mapped[Patient] = relationship("Patient")


class Consultation(Base, TimestampMixin):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes_internal: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft")

    activity: Mapped[Activity] = relationship("Activity")
    patient: Mapped[Patient] = relationship("Patient", back_populates="consultations")
    items: Mapped[List["ConsultationItem"]] = relationship(
        "ConsultationItem", back_populates="consultation", cascade="all, delete-orphan"
    )


class ConsultationItem(Base):
    __tablename__ = "consultation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"), nullable=False)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("services.id"))
    qty: Mapped[float] = mapped_column(Float, default=1.0)
    price_ht: Mapped[float] = mapped_column(Float, nullable=False)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    label_override: Mapped[Optional[str]] = mapped_column(String(255))

    consultation: Mapped[Consultation] = relationship("Consultation", back_populates="items")
    service: Mapped[Optional[Service]] = relationship("Service")


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("number", name="uq_invoice_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    total_ht: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_ttc: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    public_note: Mapped[Optional[str]] = mapped_column(Text)
    private_note: Mapped[Optional[str]] = mapped_column(Text)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(255))

    activity: Mapped[Activity] = relationship("Activity", back_populates="invoices")
    patient: Mapped[Patient] = relationship("Patient", back_populates="invoices")
    items: Mapped[List["InvoiceItem"]] = relationship(
        "InvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment", back_populates="invoice", cascade="all, delete-orphan"
    )
    credit_notes: Mapped[List["CreditNote"]] = relationship("CreditNote", back_populates="invoice")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    qty: Mapped[float] = mapped_column(Float, default=1.0)
    price_ht: Mapped[float] = mapped_column(Float, nullable=False)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_ht: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_ttc: Mapped[float] = mapped_column(Float, default=0.0)
    service_id_nullable: Mapped[Optional[int]] = mapped_column(ForeignKey("services.id"))

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="items")
    service: Mapped[Optional[Service]] = relationship("Service")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(128))

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="payments")


class CreditNote(Base):
    __tablename__ = "credit_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_ht: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_ttc: Mapped[float] = mapped_column(Float, default=0.0)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(255))

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="credit_notes")


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64))
    meta_json: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped[Optional[User]] = relationship("User")


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
