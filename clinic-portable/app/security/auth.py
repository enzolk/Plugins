from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.db.models import AuditLog, User
from app.db.session import session_scope


class AuthError(Exception):
    pass


@dataclass
class AuthResult:
    user: User


class AuthManager:
    def __init__(self, session_factory, crypto_manager, paths) -> None:
        self.session_factory = session_factory
        self.crypto = crypto_manager
        self.paths = paths
        self._ph = PasswordHasher()
        self._current_user: Optional[User] = None
        self._locked = True

    # ------------------------------------------------------------------
    def is_bootstrap_required(self) -> bool:
        with session_scope(self.session_factory) as session:
            return session.query(User).count() == 0

    def create_admin(self, email: str, password: str, master_password: str) -> User:
        if not email or not password:
            raise AuthError("Email et mot de passe requis")
        with session_scope(self.session_factory) as session:
            if session.query(User).filter(User.email == email).first():
                raise AuthError("Un utilisateur existe déjà avec cet email")
            password_hash = self._ph.hash(password)
            user = User(email=email, password_hash=password_hash)
            session.add(user)
        self.crypto.ensure_master_key(master_password)
        return user

    # ------------------------------------------------------------------
    def authenticate(self, email: str, password: str, master_password: Optional[str] = None) -> AuthResult:
        with session_scope(self.session_factory) as session:
            user = session.query(User).filter(User.email == email).first()
            if not user:
                raise AuthError("Utilisateur inconnu")
            try:
                self._ph.verify(user.password_hash, password)
            except VerifyMismatchError as exc:
                raise AuthError("Mot de passe invalide") from exc
        if master_password:
            self.crypto.unlock(master_password)
        elif not self.crypto.is_unlocked():
            raise AuthError("Le mot de passe maître est requis")
        self._current_user = user
        self._locked = False
        return AuthResult(user=user)

    def lock(self) -> None:
        self._locked = True
        self._current_user = None
        self.crypto.lock()

    def change_password(self, user: User, new_password: str) -> None:
        with session_scope(self.session_factory) as session:
            db_user = session.query(User).get(user.id)
            if not db_user:
                raise AuthError("Utilisateur introuvable")
            db_user.password_hash = self._ph.hash(new_password)

    def audit(self, action: str, entity: str, entity_id: Optional[str] = None, meta: Optional[dict] = None) -> None:
        if not self._current_user:
            return
        with session_scope(self.session_factory) as session:
            log = AuditLog(
                user_id=self._current_user.id,
                action=action,
                entity=entity,
                entity_id=entity_id,
                meta_json=json.dumps(meta or {}),
            )
            session.add(log)

    @property
    def current_user(self) -> Optional[User]:
        return self._current_user

    def is_locked(self) -> bool:
        return self._locked


__all__ = ["AuthManager", "AuthResult", "AuthError"]
