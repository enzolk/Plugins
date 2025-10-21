from __future__ import annotations

import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.platform_paths import AppPaths


def create_backup(paths: AppPaths, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        if paths.db_path.exists():
            archive.write(paths.db_path, arcname="db/clinic.sqlite")
        if paths.config_path.exists():
            archive.write(paths.config_path, arcname="config.json")
        if paths.encrypted_key_path.exists():
            archive.write(paths.encrypted_key_path, arcname="crypto.key.enc")
        if paths.files_dir.exists():
            for file in paths.files_dir.rglob("*"):
                if file.is_file():
                    archive.write(file, arcname=f"files/{file.relative_to(paths.files_dir)}")
    return output_path


def restore_backup(paths: AppPaths, backup_path: Path) -> None:
    if not backup_path.exists():
        raise FileNotFoundError(backup_path)
    with ZipFile(backup_path, "r") as archive:
        archive.extractall(paths.data_dir)
    # Move extracted DB and files to proper locations if necessary
    extracted_db = paths.data_dir / "db" / "clinic.sqlite"
    if extracted_db.exists():
        paths.db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(extracted_db), str(paths.db_path))
    extracted_config = paths.data_dir / "config.json"
    if extracted_config.exists():
        shutil.move(str(extracted_config), str(paths.config_path))
    extracted_key = paths.data_dir / "crypto.key.enc"
    if extracted_key.exists():
        shutil.move(str(extracted_key), str(paths.encrypted_key_path))
    extracted_files_dir = paths.data_dir / "files"
    if extracted_files_dir.exists():
        target_dir = paths.files_dir
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(extracted_files_dir), str(target_dir))


__all__ = ["create_backup", "restore_backup"]
