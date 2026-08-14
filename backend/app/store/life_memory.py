from __future__ import annotations

import json
import threading

from app.config import get_settings
from app.models.life_schemas import LifeProject
from app.models.schemas import JobStatus


class MemoryLifeStore:
    """In-memory + disk persistence so reload / restart won't lose projects mid-run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, LifeProject] = {}

    def _path(self, project_id: str) -> Path:
        settings = get_settings()
        root = settings.storage_path / "life" / project_id
        root.mkdir(parents=True, exist_ok=True)
        return root / "project.json"

    def _persist(self, project: LifeProject) -> None:
        path = self._path(project.id)
        path.write_text(project.model_dump_json(), encoding="utf-8")

    def _load_disk(self, project_id: str) -> LifeProject | None:
        path = self._path(project_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            project = LifeProject.model_validate(data)
            # 进程重启后内存任务已丢，避免永远卡在 running
            if project.job_status == JobStatus.running:
                project.job_status = JobStatus.failed
                project.job_error = "服务曾中断，请点「重新跑一遍」继续"
                project.current_step = None
            return project
        except Exception:  # noqa: BLE001
            return None

    def create(self, project: LifeProject) -> LifeProject:
        with self._lock:
            self._items[project.id] = project.model_copy(deep=True)
            self._persist(self._items[project.id])
            return self._items[project.id].model_copy(deep=True)

    def get(self, project_id: str) -> LifeProject | None:
        with self._lock:
            p = self._items.get(project_id)
            if p is None:
                p = self._load_disk(project_id)
                if p is not None:
                    self._items[project_id] = p
            return p.model_copy(deep=True) if p else None

    def save(self, project: LifeProject) -> LifeProject:
        with self._lock:
            self._items[project.id] = project.model_copy(deep=True)
            self._persist(self._items[project.id])
            return self._items[project.id].model_copy(deep=True)


life_store = MemoryLifeStore()
