from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.app_context import app_ctx
from app.db.session import Base
from app.db import seed
from app.domain.numbering import numbering_service


@pytest.fixture(autouse=True)
def clean_database(tmp_path):
    numbering_service._cache.clear()  # type: ignore[attr-defined]
    tmp_db = tmp_path / "clinic.sqlite"
    app_ctx._engine.dispose()
    app_ctx.paths = replace(app_ctx.paths, db_path=tmp_db)
    app_ctx._engine = create_engine(f"sqlite:///{tmp_db}", future=True)
    app_ctx._session_factory = sessionmaker(bind=app_ctx._engine, autoflush=False)
    Base.metadata.create_all(app_ctx._engine)
    seed.load_demo_data()
    yield
    app_ctx._engine.dispose()
