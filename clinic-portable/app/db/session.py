from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_engine_for_path(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(url, echo=False, future=True)
    return engine


def create_session_factory(db_path: Path):
    engine = create_engine_for_path(db_path)
    Session = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
    return Session


@contextmanager
def session_scope(session_factory: Callable[[], scoped_session]) -> Iterator:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - pass through
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["Base", "create_session_factory", "session_scope", "create_engine_for_path"]
