from __future__ import annotations

import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .db import get_session
from .templating import templates, load_locale
from .routers import (
    appointments,
    auth,
    backups,
    consultations,
    invoices,
    patients,
    reports,
    settings as settings_router,
)

settings = get_settings()
app = FastAPI(title="Clinic Local", default_response_class=HTMLResponse)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    session_cookie=settings.session_cookie_name,
    https_only=settings.session_cookie_secure,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(settings.static_path)), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


app.include_router(auth.router)
app.include_router(settings_router.router, prefix="/settings")
app.include_router(patients.router, prefix="/patients")
app.include_router(appointments.router, prefix="/appointments")
app.include_router(consultations.router, prefix="/consultations")
app.include_router(invoices.router, prefix="/invoices")
app.include_router(reports.router, prefix="/reports")
app.include_router(backups.router, prefix="/backups")


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    async with get_session() as session:
        request.state.db = session
        response = await call_next(request)
        return response


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    session_token = request.session.get("csrf_token")
    if not session_token:
        session_token = secrets.token_hex(16)
        request.session["csrf_token"] = session_token
    if request.method in {"POST", "PUT", "DELETE"}:
        token = request.headers.get("X-CSRF-Token")
        content_type = request.headers.get("content-type", "")
        if token is None and (
            content_type.startswith("application/x-www-form-urlencoded")
            or content_type.startswith("multipart/form-data")
        ):
            form = await request.form()
            token = form.get("csrf_token")
        if token != session_token:
            return HTMLResponse("Jeton CSRF invalide", status_code=400)
    response = await call_next(request)
    response.set_cookie("csrf_token", session_token, httponly=True, secure=settings.session_cookie_secure)
    return response


@app.on_event("startup")
async def startup_locale():
    load_locale()


__all__ = ["app", "templates"]
