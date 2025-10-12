from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .db import models
from .db.session import Base


@dataclass
class AppPaths:
    root: Path
    data_dir: Path
    files_dir: Path
    config_file: Path
    db_path: Path
    crypto_key: Path


class AppContext:
    """Point central d'accès aux ressources de l'application."""

    def __init__(self) -> None:
        self.paths = self._init_paths()
        self.settings: Dict[str, Any] = {}
        self._engine = create_engine(f"sqlite:///{self.paths.db_path}", future=True)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False)
        Base.metadata.create_all(self._engine)

    def _init_paths(self) -> AppPaths:
        root = Path(__file__).resolve().parent.parent
        data_dir = root / "data"
        files_dir = root / "files"
        data_dir.mkdir(parents=True, exist_ok=True)
        files_dir.mkdir(parents=True, exist_ok=True)
        config_file = root / "config.json"
        db_path = data_dir / "clinic.sqlite"
        crypto_key = data_dir / "crypto.key.enc"
        return AppPaths(
            root=root,
            data_dir=data_dir,
            files_dir=files_dir,
            config_file=config_file,
            db_path=db_path,
            crypto_key=crypto_key,
        )

    def session(self) -> Session:
        return self._session_factory()

    def load_settings(self) -> Dict[str, Any]:
        if self.paths.config_file.exists():
            with self.paths.config_file.open("r", encoding="utf-8") as f:
                self.settings = json.load(f)
        else:
            self.settings = {}
        return self.settings

    def save_settings(self, data: Dict[str, Any]) -> None:
        with self.paths.config_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.settings = data


app_ctx = AppContext()


__all__ = ["app_ctx", "AppContext", "AppPaths"]
