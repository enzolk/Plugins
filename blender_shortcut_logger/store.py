from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable


class ShortcutStore:
    """Persistent many-to-many store for shortcut <-> action links."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.edges: dict[str, set[str]] = {}
        self._listeners: list[Callable[[], None]] = []
        self.load()

    def load(self) -> None:
        if not self.file_path.exists():
            self.edges = {}
            return
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            self.edges = {}
            return

        raw_edges = payload.get("edges", {})
        self.edges = {shortcut: set(actions) for shortcut, actions in raw_edges.items() if shortcut}

    def save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"edges": {k: sorted(v) for k, v in sorted(self.edges.items())}}
        self.file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_listener(self, callback: Callable[[], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def notify(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                continue

    def add_link(self, shortcut: str, action: str) -> bool:
        if not shortcut or not action:
            return False
        before = len(self.edges.get(shortcut, set()))
        self.edges.setdefault(shortcut, set()).add(action)
        if len(self.edges[shortcut]) == before:
            return False
        self.save()
        self.notify()
        return True

    def grouped_rows(self) -> list[tuple[list[str], list[str]]]:
        """Connected-component grouping across shortcuts/actions."""
        action_to_shortcuts: dict[str, set[str]] = defaultdict(set)
        for shortcut, actions in self.edges.items():
            for action in actions:
                action_to_shortcuts[action].add(shortcut)

        seen_shortcuts: set[str] = set()
        rows: list[tuple[list[str], list[str]]] = []

        for root_shortcut in sorted(self.edges):
            if root_shortcut in seen_shortcuts:
                continue

            component_shortcuts: set[str] = set()
            component_actions: set[str] = set()
            queue: deque[tuple[str, str]] = deque([("shortcut", root_shortcut)])

            while queue:
                node_type, value = queue.popleft()
                if node_type == "shortcut":
                    if value in component_shortcuts:
                        continue
                    component_shortcuts.add(value)
                    seen_shortcuts.add(value)
                    for action in self.edges.get(value, set()):
                        if action not in component_actions:
                            queue.append(("action", action))
                else:
                    if value in component_actions:
                        continue
                    component_actions.add(value)
                    for shortcut in action_to_shortcuts.get(value, set()):
                        if shortcut not in component_shortcuts:
                            queue.append(("shortcut", shortcut))

            rows.append((sorted(component_shortcuts), sorted(component_actions)))

        return rows
