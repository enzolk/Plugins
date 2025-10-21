from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .platform_paths import AppPaths, get_app_paths
from .db.session import create_session_factory, session_scope
from .db import models  # noqa: F401 - ensure models are imported for migrations
from .security.crypto import CryptoManager
from .security.auth import AuthManager


class AppContext:
    """Conteneur centralisant les dépendances partagées par l'application."""

    def __init__(self) -> None:
        self.paths: AppPaths = get_app_paths()
        self._config_cache: Optional[Dict[str, Any]] = None
        self.session_factory = create_session_factory(self.paths.db_path)
        self.crypto = CryptoManager(self.paths)
        self.auth = AuthManager(self.session_factory, self.crypto, self.paths)

    # ------------------------------------------------------------------
    # Configuration JSON stockée dans data/config.json
    # ------------------------------------------------------------------
    def _config_path(self) -> Path:
        return self.paths.config_path

    def load_config(self) -> Dict[str, Any]:
        if self._config_cache is not None:
            return self._config_cache
        path = self._config_path()
        if not path.exists():
            self._config_cache = {}
            return self._config_cache
        with path.open("r", encoding="utf-8") as fh:
            self._config_cache = json.load(fh)
        return self._config_cache

    def save_config(self, config: Dict[str, Any]) -> None:
        path = self._config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)
        self._config_cache = config

    # ------------------------------------------------------------------
    # Accès base de données
    # ------------------------------------------------------------------
    def get_session(self):  # pragma: no cover - proxy
        return self.session_factory()

    def bootstrap_database(self) -> None:
        """Crée la base et charge les données de démonstration si nécessaire."""
        from .db.seed import seed_demo_data

        with session_scope(self.session_factory) as session:
            seed_demo_data(session, self.crypto)


__all__ = ["AppContext"]
