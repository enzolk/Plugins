from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from .models import PaymentMethod, UserRole


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: UserRole


class UserRead(ORMBase):
    id: int
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime


class ActivityCreate(BaseModel):
    code: str
    name: str
    color: str = "#1d4ed8"
    vat_rate_default: float = 0.0
    invoice_prefix: str
    revenue_account: str = "706000"
    pdf_header_html: str = ""
    pdf_footer_html: str = ""


class ActivityRead(ORMBase):
    id: int
    code: str
    name: str
    color: str
    vat_rate_default: float
    invoice_prefix: str
    next_seq: int
    revenue_account: str
    pdf_header_html: str
    pdf_footer_html: str


class ServiceCreate(BaseModel):
    activity_id: int
    code: str
    name: str
    description: Optional[str] = ""
    default_duration_min: int = 60
    price_ht: float
    vat_rate: float
    is_active: bool = True


class ServiceRead(ORMBase):
    id: int
    activity_id: int
    code: str
    name: str
    price_ht: float
    vat_rate: float
    default_duration_min: int
    is_active: bool


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    birthdate: Optional[date]
    email: Optional[EmailStr]
    phone: Optional[str]
    address_json: Dict[str, Any] = Field(default_factory=dict)
    tags_json: List[str] = Field(default_factory=list)
    notes: str = ""
    consent_rgpd: bool = False


class PatientRead(ORMBase):
    id: int
    first_name: str
    last_name: str
    birthdate: Optional[date]
    email: Optional[EmailStr]
    phone: Optional[str]
    address_json: Dict[str, Any]
    tags_json: List[str]
    consent_rgpd: bool
    created_at: datetime


class AppointmentCreate(BaseModel):
    activity_id: int
    patient_id: int
    start_dt: datetime
    end_dt: datetime
    title: str
    notes: Optional[str] = ""
    status: str = "confirmé"


class AppointmentRead(ORMBase):
    id: int
    activity_id: int
    patient_id: int
    start_dt: datetime
    end_dt: datetime
    title: str
    notes: str
    status: str


class ConsultationItemCreate(BaseModel):
    service_id: int
    qty: int = 1
    price_ht: float
    vat_rate: float
    label_override: Optional[str]


class ConsultationCreate(BaseModel):
    activity_id: int
    patient_id: int
    date: date
    notes_internal: Optional[str] = ""
    status: str = "à facturer"
    items: List[ConsultationItemCreate] = Field(default_factory=list)


class ConsultationItemRead(ORMBase):
    id: int
    service_id: int
    qty: int
    price_ht: float
    vat_rate: float
    label_override: Optional[str]


class ConsultationRead(ORMBase):
    id: int
    activity_id: int
    patient_id: int
    date: date
    notes_internal: str
    status: str
    items: List[ConsultationItemRead]


class InvoiceItemCreate(BaseModel):
    label: str
    qty: int = 1
    price_ht: float
    vat_rate: float
    service_id: Optional[int]


class InvoiceCreate(BaseModel):
    activity_id: int
    patient_id: int
    date: date
    notes_public: str = ""
    notes_private: str = ""
    items: List[InvoiceItemCreate] = Field(default_factory=list)


class InvoiceItemRead(ORMBase):
    id: int
    label: str
    qty: int
    price_ht: float
    vat_rate: float
    total_ht: float
    total_vat: float
    total_ttc: float
    service_id: Optional[int]


class PaymentCreate(BaseModel):
    date: date
    method: PaymentMethod
    amount: float
    ref: Optional[str]


class PaymentRead(ORMBase):
    id: int
    date: date
    method: PaymentMethod
    amount: float
    ref: Optional[str]


class InvoiceRead(ORMBase):
    id: int
    number: str
    date: date
    status: str
    total_ht: float
    total_vat: float
    total_ttc: float
    currency: str
    notes_public: str
    notes_private: str
    activity_id: int
    patient_id: int
    items: List[InvoiceItemRead]
    payments: List[PaymentRead]


class BackupResult(BaseModel):
    path: str
    size: int


class SalesExportRow(BaseModel):
    date: date
    invoice_number: str
    patient: str
    base_ht: float
    vat: float
    total_ttc: float
    account: str
    payment_method: Optional[str]


class ReportSummary(BaseModel):
    activity_code: str
    period: str
    total_ht: float
    total_ttc: float
    total_vat: float
    unpaid: float
    consultations: int

