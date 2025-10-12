from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from passlib.hash import argon2

from ..app_context import app_ctx
from ..db import models


@dataclass
class AuthResult:
    success: bool
    user: Optional[models.User] = None
    error: Optional[str] = None


class AuthService:
    """Gestion simple de l'authentification utilisateur."""

    def __init__(self) -> None:
        self._last_auth: Optional[dt.datetime] = None

    def create_admin(self, email: str, password: str) -> models.User:
        hashed = argon2.hash(password)
        with app_ctx.session() as session:
            user = models.User(email=email, password_hash=hashed)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def authenticate(self, email: str, password: str) -> AuthResult:
        with app_ctx.session() as session:
            user = session.query(models.User).filter(models.User.email == email).first()
            if not user:
                return AuthResult(False, error="Utilisateur inconnu")
            if not argon2.verify(password, user.password_hash):
                return AuthResult(False, error="Mot de passe invalide")
            self._last_auth = dt.datetime.utcnow()
            return AuthResult(True, user=user)

    def needs_reauth(self, timeout_minutes: int = 15) -> bool:
        if self._last_auth is None:
            return True
        return dt.datetime.utcnow() - self._last_auth > dt.timedelta(minutes=timeout_minutes)


auth_service = AuthService()


__all__ = ["auth_service", "AuthService", "AuthResult"]
