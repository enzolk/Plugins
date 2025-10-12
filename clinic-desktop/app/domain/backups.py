from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from ..app_context import app_ctx


def create_backup(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(app_ctx.paths.db_path, arcname="data/clinic.sqlite")
        files_dir = app_ctx.paths.root / "files"
        for file in files_dir.rglob("*"):
            if file.is_file():
                archive.write(file, arcname=f"files/{file.relative_to(files_dir)}")
        if app_ctx.paths.config_file.exists():
            archive.write(app_ctx.paths.config_file, arcname="config.json")
        if app_ctx.paths.crypto_key.exists():
            archive.write(app_ctx.paths.crypto_key, arcname="crypto.key.enc")
    return target


def restore_backup(source: Path, destination: Path | None = None) -> None:
    destination = destination or app_ctx.paths.root
    with zipfile.ZipFile(source, "r") as archive:
        archive.extractall(destination)


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Gestion des sauvegardes Clinic")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args()

    if args.backup:
        path = create_backup(args.backup)
        print(f"Sauvegarde créée: {path}")
    if args.restore:
        restore_backup(args.restore)
        print("Restauration terminée")


if __name__ == "__main__":
    _cli()
