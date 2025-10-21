from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


@dataclass
class CryptoState:
    salt: bytes
    encrypted_key: bytes


class CryptoError(Exception):
    pass


class CryptoManager:
    def __init__(self, paths) -> None:
        self.paths = paths
        self._fernet: Optional[Fernet] = None
        self._salt: Optional[bytes] = None
        self._encrypted_key: Optional[bytes] = None
        self._loaded = False

    # ------------------------------------------------------------------
    def _load_state(self) -> Optional[CryptoState]:
        if self._loaded:
            if self._salt and self._encrypted_key:
                return CryptoState(self._salt, self._encrypted_key)
            return None
        path = self.paths.encrypted_key_path
        if not path.exists():
            self._loaded = True
            return None
        with path.open("rb") as fh:
            data = json.loads(fh.read().decode("utf-8"))
        salt = base64.urlsafe_b64decode(data["salt"])
        encrypted_key = base64.urlsafe_b64decode(data["key"])
        self._salt = salt
        self._encrypted_key = encrypted_key
        self._loaded = True
        return CryptoState(salt, encrypted_key)

    def _save_state(self, state: CryptoState) -> None:
        payload = {
            "salt": base64.urlsafe_b64encode(state.salt).decode("utf-8"),
            "key": base64.urlsafe_b64encode(state.encrypted_key).decode("utf-8"),
        }
        path = self.paths.encrypted_key_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        self._salt = state.salt
        self._encrypted_key = state.encrypted_key
        self._loaded = True

    # ------------------------------------------------------------------
    @staticmethod
    def _derive(password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=390000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    def ensure_master_key(self, password: str) -> None:
        if self._load_state() is not None:
            return
        salt = os.urandom(16)
        master_key = Fernet.generate_key()
        derived = self._derive(password, salt)
        encrypted_key = Fernet(derived).encrypt(master_key)
        self._save_state(CryptoState(salt, encrypted_key))
        self._fernet = Fernet(master_key)

    def unlock(self, password: str) -> None:
        state = self._load_state()
        if state is None:
            raise CryptoError("Aucune clé maître trouvée")
        derived = self._derive(password, state.salt)
        try:
            master_key = Fernet(derived).decrypt(state.encrypted_key)
        except InvalidToken as exc:  # pragma: no cover - incorrect password
            raise CryptoError("Mot de passe maître invalide") from exc
        self._fernet = Fernet(master_key)

    def is_unlocked(self) -> bool:
        return self._fernet is not None

    def lock(self) -> None:
        self._fernet = None

    def encrypt(self, plaintext: str) -> bytes:
        if not self.is_unlocked():
            raise CryptoError("Le coffre est verrouillé")
        assert self._fernet is not None
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: Optional[bytes]) -> str:
        if not ciphertext:
            return ""
        if not self.is_unlocked():
            raise CryptoError("Le coffre est verrouillé")
        assert self._fernet is not None
        try:
            data = self._fernet.decrypt(ciphertext)
        except InvalidToken as exc:  # pragma: no cover - data corruption
            raise CryptoError("Impossible de déchiffrer les données") from exc
        return data.decode("utf-8")

    def change_master_password(self, current_password: str, new_password: str) -> None:
        state = self._load_state()
        if state is None:
            raise CryptoError("Aucune clé maître à mettre à jour")
        derived_old = self._derive(current_password, state.salt)
        try:
            master_key = Fernet(derived_old).decrypt(state.encrypted_key)
        except InvalidToken as exc:
            raise CryptoError("Mot de passe actuel invalide") from exc
        new_salt = os.urandom(16)
        derived_new = self._derive(new_password, new_salt)
        encrypted_key = Fernet(derived_new).encrypt(master_key)
        self._save_state(CryptoState(new_salt, encrypted_key))
        self._fernet = Fernet(master_key)


__all__ = ["CryptoManager", "CryptoError"]
