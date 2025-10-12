import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from zipfile import ZipFile, ZIP_DEFLATED

from ..config import get_settings


def backup(target: Optional[Path] = None) -> Path:
    settings = get_settings()
    target_dir = settings.base_path / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    if target is None:
        target = target_dir / f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"

    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        db_path = settings.data_path / "db.sqlite"
        if db_path.exists():
            archive.write(db_path, arcname="db.sqlite")
        files_dir = settings.files_path
        if files_dir.exists():
            for path in files_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, arcname=str(Path("files") / path.relative_to(files_dir)))
        config_path = settings.base_path / "config.json"
        if config_path.exists():
            archive.write(config_path, arcname="config.json")
    return target


def restore(archive_path: Path) -> None:
    settings = get_settings()
    with ZipFile(archive_path, "r") as archive:
        temp_dir = settings.base_path / "_restore_tmp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        archive.extractall(temp_dir)
        db_source = temp_dir / "db.sqlite"
        if db_source.exists():
            (settings.data_path).mkdir(parents=True, exist_ok=True)
            shutil.move(db_source, settings.data_path / "db.sqlite")
        files_dir = temp_dir / "files"
        if files_dir.exists():
            target_files = settings.files_path
            target_files.mkdir(parents=True, exist_ok=True)
            for item in files_dir.rglob("*"):
                dest = target_files / item.relative_to(files_dir)
                if item.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(item, dest)
        config_file = temp_dir / "config.json"
        if config_file.exists():
            shutil.move(config_file, settings.base_path / "config.json")
        shutil.rmtree(temp_dir)

