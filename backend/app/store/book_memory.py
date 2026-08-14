from __future__ import annotations

import threading
from pathlib import Path

from app.config import get_settings
from app.models.book_schemas import BookProject


class MemoryBookStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, BookProject] = {}

    def next_book_seq(self) -> int:
        """Persist a global「第 N 本」counter under storage."""
        settings = get_settings()
        path = Path(settings.storage_path) / "_book_seq.txt"
        with self._lock:
            current = 148
            if path.exists():
                try:
                    current = int(path.read_text(encoding="utf-8").strip() or "148")
                except ValueError:
                    current = 148
            nxt = current + 1
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(nxt), encoding="utf-8")
            return nxt

    def create(self, project: BookProject) -> BookProject:
        with self._lock:
            self._items[project.id] = project.model_copy(deep=True)
            return self._items[project.id].model_copy(deep=True)

    def get(self, project_id: str) -> BookProject | None:
        with self._lock:
            p = self._items.get(project_id)
            return p.model_copy(deep=True) if p else None

    def save(self, project: BookProject) -> BookProject:
        with self._lock:
            self._items[project.id] = project.model_copy(deep=True)
            return self._items[project.id].model_copy(deep=True)


book_store = MemoryBookStore()
