from __future__ import annotations

import threading

from app.models.outfit_schemas import OutfitProject


class MemoryOutfitStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, OutfitProject] = {}

    def create(self, project: OutfitProject) -> OutfitProject:
        with self._lock:
            self._items[project.id] = project.model_copy(deep=True)
            return self._items[project.id].model_copy(deep=True)

    def get(self, project_id: str) -> OutfitProject | None:
        with self._lock:
            p = self._items.get(project_id)
            return p.model_copy(deep=True) if p else None

    def save(self, project: OutfitProject) -> OutfitProject:
        with self._lock:
            self._items[project.id] = project.model_copy(deep=True)
            return self._items[project.id].model_copy(deep=True)


outfit_store = MemoryOutfitStore()
