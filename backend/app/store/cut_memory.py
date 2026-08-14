from __future__ import annotations

from app.models.cut_schemas import CutProject


class MemoryCutStore:
    def __init__(self) -> None:
        self._items: dict[str, CutProject] = {}

    def create(self, project: CutProject) -> CutProject:
        self._items[project.id] = project
        return project

    def get(self, project_id: str) -> CutProject | None:
        return self._items.get(project_id)

    def save(self, project: CutProject) -> CutProject:
        self._items[project.id] = project
        return project


cut_store = MemoryCutStore()
