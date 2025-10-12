from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db
from ..models import User
from ..security import hash_password, verify_password
from ..templating import templates

router = APIRouter()


@router.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": None})


@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Identifiants invalides"},
            status_code=400,
        )
    request.session["user_id"] = user.id
    response = RedirectResponse(url="/", status_code=302)
    return response


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


async def create_user(db: AsyncSession, email: str, password: str, role: str = "admin") -> User:
    user = User(email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    await db.flush()
    return user

