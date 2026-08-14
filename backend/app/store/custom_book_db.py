from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from app.models.custom_book_schemas import OrderStatus, PageStatus, utcnow

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "custom_book.db"


def _new_id(n: int = 10) -> str:
    return uuid.uuid4().hex[:n]


class CustomBookStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS orders (
                        id TEXT PRIMARY KEY,
                        child_name TEXT NOT NULL,
                        age INTEGER NOT NULL,
                        gender TEXT NOT NULL,
                        theme TEXT NOT NULL,
                        emotion_goal TEXT NOT NULL DEFAULT '',
                        parent_message TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL,
                        title TEXT NOT NULL DEFAULT '',
                        story_json TEXT,
                        character_regen_count INTEGER NOT NULL DEFAULT 0,
                        pdf_path TEXT,
                        error TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS order_photos (
                        id TEXT PRIMARY KEY,
                        order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                        path TEXT NOT NULL,
                        sort_order INTEGER NOT NULL,
                        quality_score REAL NOT NULL DEFAULT 0
                    );

                    CREATE TABLE IF NOT EXISTS character_profiles (
                        id TEXT PRIMARY KEY,
                        order_id TEXT NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
                        name TEXT NOT NULL,
                        age INTEGER NOT NULL,
                        face_shape TEXT NOT NULL DEFAULT '',
                        hair TEXT NOT NULL DEFAULT '',
                        eyes TEXT NOT NULL DEFAULT '',
                        skin TEXT NOT NULL DEFAULT '',
                        special_features TEXT NOT NULL DEFAULT '',
                        clothing_style TEXT NOT NULL DEFAULT '',
                        character_prompt TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'draft',
                        confirmed_at TEXT
                    );

                    CREATE TABLE IF NOT EXISTS character_assets (
                        id TEXT PRIMARY KEY,
                        profile_id TEXT NOT NULL REFERENCES character_profiles(id) ON DELETE CASCADE,
                        view_type TEXT NOT NULL,
                        path TEXT NOT NULL,
                        generation INTEGER NOT NULL DEFAULT 1
                    );

                    CREATE TABLE IF NOT EXISTS pages (
                        id TEXT PRIMARY KEY,
                        order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                        page_no INTEGER NOT NULL,
                        text TEXT NOT NULL DEFAULT '',
                        scene_prompt TEXT NOT NULL DEFAULT '',
                        emotion TEXT NOT NULL DEFAULT '',
                        image_path TEXT,
                        status TEXT NOT NULL DEFAULT 'pending',
                        regen_count INTEGER NOT NULL DEFAULT 0,
                        version INTEGER NOT NULL DEFAULT 1,
                        UNIQUE(order_id, page_no)
                    );
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def create_order(
        self,
        *,
        child_name: str,
        age: int,
        gender: str,
        theme: str,
        emotion_goal: str,
    ) -> dict[str, Any]:
        order_id = _new_id()
        now = utcnow().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO orders (
                        id, child_name, age, gender, theme, emotion_goal,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        child_name,
                        age,
                        gender,
                        theme,
                        emotion_goal,
                        OrderStatus.draft.value,
                        now,
                        now,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_order(order_id)  # type: ignore[return-value]

    def list_orders(self) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT id, child_name, age, theme, status, title, updated_at
                    FROM orders ORDER BY updated_at DESC
                    """
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM orders WHERE id = ?", (order_id,)
                ).fetchone()
                if not row:
                    return None
                order = dict(row)
                order["photos"] = [
                    dict(r)
                    for r in conn.execute(
                        """
                        SELECT * FROM order_photos
                        WHERE order_id = ? ORDER BY sort_order ASC
                        """,
                        (order_id,),
                    ).fetchall()
                ]
                profile = conn.execute(
                    "SELECT * FROM character_profiles WHERE order_id = ?",
                    (order_id,),
                ).fetchone()
                order["character"] = dict(profile) if profile else None
                if profile:
                    order["character_assets"] = [
                        dict(r)
                        for r in conn.execute(
                            """
                            SELECT * FROM character_assets
                            WHERE profile_id = ?
                            ORDER BY generation DESC, view_type ASC
                            """,
                            (profile["id"],),
                        ).fetchall()
                    ]
                else:
                    order["character_assets"] = []
                order["pages"] = [
                    dict(r)
                    for r in conn.execute(
                        """
                        SELECT * FROM pages
                        WHERE order_id = ? ORDER BY page_no ASC
                        """,
                        (order_id,),
                    ).fetchall()
                ]
                return order
            finally:
                conn.close()

    def update_order(self, order_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields = {**fields, "updated_at": utcnow().isoformat()}
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [order_id]
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(f"UPDATE orders SET {cols} WHERE id = ?", values)
                conn.commit()
            finally:
                conn.close()

    def add_photos(
        self,
        order_id: str,
        photos: list[tuple[str, int, float]],
    ) -> None:
        """photos: list of (path, sort_order, quality_score)"""
        with self._lock:
            conn = self._connect()
            try:
                for path, sort_order, score in photos:
                    conn.execute(
                        """
                        INSERT INTO order_photos (id, order_id, path, sort_order, quality_score)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (_new_id(12), order_id, path, sort_order, score),
                    )
                conn.commit()
            finally:
                conn.close()

    def upsert_character_profile(
        self,
        order_id: str,
        *,
        name: str,
        age: int,
        face_shape: str,
        hair: str,
        eyes: str,
        skin: str,
        special_features: str,
        clothing_style: str,
        character_prompt: str,
        status: str = "draft",
    ) -> str:
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT id FROM character_profiles WHERE order_id = ?",
                    (order_id,),
                ).fetchone()
                if existing:
                    profile_id = existing["id"]
                    conn.execute(
                        """
                        UPDATE character_profiles SET
                            name=?, age=?, face_shape=?, hair=?, eyes=?, skin=?,
                            special_features=?, clothing_style=?, character_prompt=?,
                            status=?, confirmed_at=NULL
                        WHERE id=?
                        """,
                        (
                            name,
                            age,
                            face_shape,
                            hair,
                            eyes,
                            skin,
                            special_features,
                            clothing_style,
                            character_prompt,
                            status,
                            profile_id,
                        ),
                    )
                else:
                    profile_id = _new_id(12)
                    conn.execute(
                        """
                        INSERT INTO character_profiles (
                            id, order_id, name, age, face_shape, hair, eyes, skin,
                            special_features, clothing_style, character_prompt, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            profile_id,
                            order_id,
                            name,
                            age,
                            face_shape,
                            hair,
                            eyes,
                            skin,
                            special_features,
                            clothing_style,
                            character_prompt,
                            status,
                        ),
                    )
                conn.commit()
                return profile_id
            finally:
                conn.close()

    def update_character_prompt(self, order_id: str, character_prompt: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE character_profiles SET character_prompt = ?
                    WHERE order_id = ?
                    """,
                    (character_prompt, order_id),
                )
                conn.execute(
                    "UPDATE orders SET updated_at = ? WHERE id = ?",
                    (utcnow().isoformat(), order_id),
                )
                conn.commit()
            finally:
                conn.close()

    def confirm_character(self, order_id: str) -> None:
        now = utcnow().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE character_profiles
                    SET status = 'confirmed', confirmed_at = ?
                    WHERE order_id = ?
                    """,
                    (now, order_id),
                )
                conn.execute(
                    """
                    UPDATE orders SET status = ?, updated_at = ? WHERE id = ?
                    """,
                    (OrderStatus.character_confirmed.value, now, order_id),
                )
                conn.commit()
            finally:
                conn.close()

    def replace_character_assets(
        self,
        profile_id: str,
        assets: list[tuple[str, str, int]],
    ) -> None:
        """assets: (view_type, path, generation)"""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "DELETE FROM character_assets WHERE profile_id = ?",
                    (profile_id,),
                )
                for view_type, path, generation in assets:
                    conn.execute(
                        """
                        INSERT INTO character_assets (id, profile_id, view_type, path, generation)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (_new_id(12), profile_id, view_type, path, generation),
                    )
                conn.commit()
            finally:
                conn.close()

    def replace_pages(
        self,
        order_id: str,
        pages: list[dict[str, str]],
    ) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM pages WHERE order_id = ?", (order_id,))
                for p in pages:
                    conn.execute(
                        """
                        INSERT INTO pages (
                            id, order_id, page_no, text, scene_prompt, emotion, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _new_id(12),
                            order_id,
                            int(p["page"]),
                            p.get("text", ""),
                            p.get("scene_prompt", ""),
                            p.get("emotion", ""),
                            PageStatus.pending.value,
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

    def update_page(self, order_id: str, page_no: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [order_id, page_no]
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    f"UPDATE pages SET {cols} WHERE order_id = ? AND page_no = ?",
                    values,
                )
                conn.execute(
                    "UPDATE orders SET updated_at = ? WHERE id = ?",
                    (utcnow().isoformat(), order_id),
                )
                conn.commit()
            finally:
                conn.close()

    def get_page(self, order_id: str, page_no: int) -> dict[str, Any] | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM pages WHERE order_id = ? AND page_no = ?",
                    (order_id, page_no),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def set_story(self, order_id: str, title: str, story: dict[str, Any]) -> None:
        self.update_order(
            order_id,
            title=title,
            story_json=json.dumps(story, ensure_ascii=False),
            status=OrderStatus.story_ready.value,
        )


custom_book_store = CustomBookStore()
