from __future__ import annotations

import threading
from typing import Protocol

from app.models.schemas import Project


class ProjectStore(Protocol):
    def create(self, project: Project) -> Project: ...
    def get(self, project_id: str) -> Project | None: ...
    def save(self, project: Project) -> Project: ...
    def list_ids(self) -> list[str]: ...


class MemoryProjectStore:
    """In-memory store — swap for Redis/Postgres later behind ProjectStore."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._projects: dict[str, Project] = {}

    def create(self, project: Project) -> Project:
        with self._lock:
            self._projects[project.id] = project.model_copy(deep=True)
            return self._projects[project.id].model_copy(deep=True)

    def get(self, project_id: str) -> Project | None:
        with self._lock:
            p = self._projects.get(project_id)
            return p.model_copy(deep=True) if p else None

    def save(self, project: Project) -> Project:
        with self._lock:
            self._projects[project.id] = project.model_copy(deep=True)
            return self._projects[project.id].model_copy(deep=True)

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._projects.keys())


store = MemoryProjectStore()
