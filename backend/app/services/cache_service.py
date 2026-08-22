import sqlite3
import json
import time
from pathlib import Path
from typing import Any, Optional
from ..config import BASE_DIR

DB_PATH = BASE_DIR / "cache.db"

class CacheService:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_store (
                    cache_key TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl REAL NOT NULL
                )
            """)
            conn.commit()

    def get(self, category: str, key: str) -> Optional[Any]:
        composite_key = f"{category}:{key}"
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT data, created_at, ttl FROM cache_store WHERE cache_key = ?",
                (composite_key,)
            )
            row = cursor.fetchone()
            if row:
                if now - row["created_at"] < row["ttl"]:
                    try:
                        return json.loads(row["data"])
                    except Exception:
                        return None
                else:
                    # 만료된 캐시 삭제
                    conn.execute("DELETE FROM cache_store WHERE cache_key = ?", (composite_key,))
                    conn.commit()
        return None

    def set(self, category: str, key: str, data: Any, ttl: float):
        composite_key = f"{category}:{key}"
        now = time.time()
        json_data = json.dumps(data, ensure_ascii=False)
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache_store (cache_key, category, data, created_at, ttl)
                VALUES (?, ?, ?, ?, ?)
            """, (composite_key, category, json_data, now, ttl))
            conn.commit()

    def clear(self, category: Optional[str] = None):
        with self._get_connection() as conn:
            if category:
                conn.execute("DELETE FROM cache_store WHERE category = ?", (category,))
            else:
                conn.execute("DELETE FROM cache_store")
            conn.commit()

cache_service = CacheService()
