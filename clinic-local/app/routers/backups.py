from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, RedirectResponse

from ..config import get_settings
from ..templating import templates
from ..services import backups

router = APIRouter()


@router.get("/")
async def backups_index(request: Request):
    settings = get_settings()
    backup_dir = settings.base_path / "backups"
    files = sorted(backup_dir.glob("*.zip")) if backup_dir.exists() else []
    return templates.TemplateResponse(
        "backups/index.html",
        {"request": request, "files": files},
    )


@router.post("/")
async def create_backup():
    backups.backup()
    return RedirectResponse("/backups", status_code=302)


@router.get("/download")
async def download_backup(path: str):
    settings = get_settings()
    file_path = settings.base_path / Path(path)
    if not file_path.exists():
        return RedirectResponse("/backups", status_code=302)
    return FileResponse(file_path)


@router.post("/restore")
async def restore_backup(path: str = Form(...)):
    settings = get_settings()
    backups.restore(settings.base_path / Path(path))
    return RedirectResponse("/backups", status_code=302)
