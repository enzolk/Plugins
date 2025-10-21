from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir

APP_NAME = "ClinicPortable"
APP_AUTHOR = "ClinicPortable"


@dataclass
class AppPaths:
    base_dir: Path
    data_dir: Path
    db_path: Path
    files_dir: Path
    logs_dir: Path
    backups_dir: Path
    config_path: Path
    encrypted_key_path: Path
    pdf_templates_dir: Path

    def ensure(self) -> "AppPaths":
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return self

    def invoices_dir_for_year(self, year: int) -> Path:
        path = self.files_dir / "invoices" / str(year)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def default_log_path(self) -> Path:
        return self.logs_dir / "app.log"


def _portable_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def _preferred_data_dir(base_dir: Path) -> Optional[Path]:
    portable_data = base_dir / "data"
    try:
        portable_data.mkdir(parents=True, exist_ok=True)
        test_file = portable_data / ".writable"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return portable_data
    except OSError:
        return None


def _fallback_data_dir() -> Path:
    data_root = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    data_root.mkdir(parents=True, exist_ok=True)
    return data_root


def get_app_paths() -> AppPaths:
    base_dir = _portable_base_dir()
    data_dir = _preferred_data_dir(base_dir) or _fallback_data_dir()

    db_path = data_dir / "db" / "clinic.sqlite"
    files_dir = data_dir / "files"
    logs_dir = data_dir / "logs"
    backups_dir = data_dir / "backups"
    config_path = data_dir / "config.json"
    encrypted_key_path = data_dir / "crypto.key.enc"

    pdf_templates_dir = base_dir / "files" / "pdf_templates"
    if not pdf_templates_dir.exists():
        pdf_templates_dir = Path(getattr(sys, "_MEIPASS", base_dir)) / "pdf_templates"

    return AppPaths(
        base_dir=base_dir,
        data_dir=data_dir,
        db_path=db_path,
        files_dir=files_dir,
        logs_dir=logs_dir,
        backups_dir=backups_dir,
        config_path=config_path,
        encrypted_key_path=encrypted_key_path,
        pdf_templates_dir=pdf_templates_dir,
    ).ensure()


__all__ = ["AppPaths", "get_app_paths", "APP_NAME"]
