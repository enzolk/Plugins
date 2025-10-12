"""Initial schema"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

revision = "202405010001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "activities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(10), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), nullable=False, server_default="#1d4ed8"),
        sa.Column("vat_rate_default", sa.Float, nullable=False, server_default="0"),
        sa.Column("invoice_prefix", sa.String(10), nullable=False),
        sa.Column("next_seq", sa.Integer, nullable=False, server_default="1"),
        sa.Column("revenue_account", sa.String(20), nullable=False, server_default="706000"),
        sa.Column("pdf_header_html", sa.Text, nullable=False, server_default=""),
        sa.Column("pdf_footer_html", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "services",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("activity_id", sa.Integer, sa.ForeignKey("activities.id"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("default_duration_min", sa.Integer, nullable=False, server_default="60"),
        sa.Column("price_ht", sa.Float, nullable=False, server_default="0"),
        sa.Column("vat_rate", sa.Float, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "patients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("first_name", sa.String(120), nullable=False),
        sa.Column("last_name", sa.String(120), nullable=False),
        sa.Column("birthdate", sa.Date, nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address_json", sqlite.JSON, nullable=False, server_default="{}"),
        sa.Column("tags_json", sqlite.JSON, nullable=False, server_default="[]"),
        sa.Column("notes_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("consent_rgpd", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_patient_identity", "patients", ["first_name", "last_name", "birthdate"])

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("activity_id", sa.Integer, sa.ForeignKey("activities.id"), nullable=False),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("start_dt", sa.DateTime, nullable=False),
        sa.Column("end_dt", sa.DateTime, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="confirmé"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "consultations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("activity_id", sa.Integer, sa.ForeignKey("activities.id"), nullable=False),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("notes_internal", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="à facturer"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "consultation_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("consultation_id", sa.Integer, sa.ForeignKey("consultations.id"), nullable=False),
        sa.Column("service_id", sa.Integer, sa.ForeignKey("services.id"), nullable=False),
        sa.Column("qty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("price_ht", sa.Float, nullable=False, server_default="0"),
        sa.Column("vat_rate", sa.Float, nullable=False, server_default="0"),
        sa.Column("label_override", sa.String(255), nullable=True),
    )

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("activity_id", sa.Integer, sa.ForeignKey("activities.id"), nullable=False),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("number", sa.String(50), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="brouillon"),
        sa.Column("total_ht", sa.Float, nullable=False, server_default="0"),
        sa.Column("total_vat", sa.Float, nullable=False, server_default="0"),
        sa.Column("total_ttc", sa.Float, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("notes_public", sa.Text, nullable=False, server_default=""),
        sa.Column("notes_private", sa.Text, nullable=False, server_default=""),
        sa.Column("pdf_path", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("qty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("price_ht", sa.Float, nullable=False, server_default="0"),
        sa.Column("vat_rate", sa.Float, nullable=False, server_default="0"),
        sa.Column("total_ht", sa.Float, nullable=False, server_default="0"),
        sa.Column("total_vat", sa.Float, nullable=False, server_default="0"),
        sa.Column("total_ttc", sa.Float, nullable=False, server_default="0"),
        sa.Column("service_id", sa.Integer, sa.ForeignKey("services.id"), nullable=True),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("ref", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "credit_notes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("number", sa.String(50), nullable=False, unique=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("total_ht", sa.Float, nullable=False, server_default="0"),
        sa.Column("total_vat", sa.Float, nullable=False, server_default="0"),
        sa.Column("total_ttc", sa.Float, nullable=False, server_default="0"),
        sa.Column("pdf_path", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_name", sa.String(200), nullable=False, server_default="Cabinet local"),
        sa.Column("siret", sa.String(50), nullable=False, server_default=""),
        sa.Column("vat_number", sa.String(50), nullable=False, server_default=""),
        sa.Column("address_json", sqlite.JSON, nullable=False, server_default="{}"),
        sa.Column("iban_bic", sqlite.JSON, nullable=False, server_default="{}"),
        sa.Column("logo_path", sa.String(255), nullable=True),
        sa.Column("locale", sa.String(10), nullable=False, server_default="fr"),
        sa.Column("fiscal_year_start_month", sa.Integer, nullable=False, server_default="1"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(50), nullable=True),
        sa.Column("meta_json", sqlite.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


    op.create_index("ix_patient_name", "patients", ["last_name", "first_name"])
    op.create_index("ix_invoice_number", "invoices", ["number"])
    op.create_index("ix_invoice_activity", "invoices", ["activity_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_activity", table_name="invoices")
    op.drop_index("ix_invoice_number", table_name="invoices")
    op.drop_index("ix_patient_name", table_name="patients")
    op.drop_table("audit_logs")
    op.drop_table("settings")
    op.drop_table("credit_notes")
    op.drop_table("payments")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("consultation_items")
    op.drop_table("consultations")
    op.drop_table("appointments")
    op.drop_constraint("uq_patient_identity", "patients", type_="unique")
    op.drop_table("patients")
    op.drop_table("services")
    op.drop_table("activities")
    op.drop_table("users")

