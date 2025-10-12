from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..app_context import app_ctx


@dataclass
class EncryptionContext:
    master_password_hash: Optional[bytes]
    salt: bytes


class CryptoManager:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fernet: Optional[Fernet] = None
        self._context: Optional[EncryptionContext] = None

    def initialize(self, master_password: str) -> None:
        salt = os.urandom(16)
        key = self._derive_key(master_password, salt)
        fernet_key = Fernet.generate_key()
        token = Fernet(key).encrypt(fernet_key)
        with self.path.open("wb") as f:
            f.write(salt + token)
        self._fernet = Fernet(fernet_key)
        self._context = EncryptionContext(master_password_hash=key, salt=salt)

    def load(self, master_password: str) -> None:
        data = self.path.read_bytes()
        salt, token = data[:16], data[16:]
        key = self._derive_key(master_password, salt)
        try:
            fernet_key = Fernet(key).decrypt(token)
        except InvalidToken as exc:
            raise ValueError("Mot de passe maître incorrect") from exc
        self._fernet = Fernet(fernet_key)
        self._context = EncryptionContext(master_password_hash=key, salt=salt)

    def encrypt(self, message: str) -> str:
        if not self._fernet:
            raise RuntimeError("Contexte de chiffrement non initialisé")
        return self._fernet.encrypt(message.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        if not self._fernet:
            raise RuntimeError("Contexte de chiffrement non initialisé")
        return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=390_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


crypto_manager = CryptoManager(app_ctx.paths.crypto_key)


__all__ = ["crypto_manager", "CryptoManager"]
