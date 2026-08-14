from __future__ import annotations

from app.models.xhs_schemas import XhsProject


class MemoryXhsStore:
    def __init__(self) -> None:
        self._items: dict[str, XhsProject] = {}

    def create(self, project: XhsProject) -> XhsProject:
        self._items[project.id] = project
        return project

    def get(self, project_id: str) -> XhsProject | None:
        return self._items.get(project_id)

    def save(self, project: XhsProject) -> XhsProject:
        self._items[project.id] = project
        return project


xhs_store = MemoryXhsStore()
