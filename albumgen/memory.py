"""Album memory: one SQLite file. Remembers what was generated so the sampler can avoid repeats,
and stores per-page feedback so position weights learn from bad renders."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS albums (
  album_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  seed INTEGER,
  theme_id TEXT NOT NULL,
  family TEXT,
  arc_id TEXT NOT NULL,
  location_id TEXT NOT NULL,
  her_outfit_id TEXT NOT NULL,
  his_outfit_id TEXT,
  reference_mode TEXT,
  character_fp TEXT NOT NULL,
  character TEXT,
  positions TEXT NOT NULL,
  title TEXT,
  logline TEXT,
  llm_model TEXT,
  status TEXT NOT NULL DEFAULT 'generated'
);
CREATE INDEX IF NOT EXISTS albums_created ON albums(created_at);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  album_id TEXT NOT NULL,
  shot INTEGER NOT NULL,
  position_id TEXT,
  verdict TEXT NOT NULL CHECK (verdict IN ('good','bad')),
  reason TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS feedback_position ON feedback(position_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Memory:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ---- reads used by the sampler ----
    def recent(self, n: int) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM albums WHERE status != 'discarded' ORDER BY created_at DESC, rowid DESC LIMIT ?", (n,)
        ).fetchall()

    def counts(self, column: str) -> Counter:
        assert column in ("theme_id", "arc_id", "family", "location_id", "her_outfit_id")
        rows = self.db.execute(f"SELECT {column} AS k, COUNT(*) AS c FROM albums WHERE status != 'discarded' GROUP BY {column}")
        return Counter({r["k"]: r["c"] for r in rows})

    def recent_themes(self, n: int) -> set[str]:
        return {r["theme_id"] for r in self.recent(n)}

    def recent_pairs(self, n: int) -> set[tuple[str, str]]:
        return {(r["location_id"], r["her_outfit_id"]) for r in self.recent(n)}

    def recent_positions(self, n: int) -> Counter:
        c: Counter = Counter()
        for r in self.recent(n):
            c.update(json.loads(r["positions"]))
        return c

    def position_counts(self) -> Counter:
        """How often each pose was used in all remembered albums (a pose never used yet gets a novelty boost)."""
        c: Counter = Counter()
        for r in self.db.execute("SELECT positions FROM albums WHERE status != 'discarded'"):
            c.update(json.loads(r["positions"]))
        return c

    def has_fingerprint(self, fp: str) -> bool:
        return self.db.execute("SELECT 1 FROM albums WHERE character_fp = ? LIMIT 1", (fp,)).fetchone() is not None

    def recent_titles(self, n: int) -> list[dict[str, str]]:
        return [{"title": r["title"] or "", "logline": r["logline"] or ""} for r in self.recent(n) if r["title"]]

    def position_stats(self) -> dict[str, tuple[int, int]]:
        rows = self.db.execute(
            "SELECT position_id, SUM(verdict='good') AS g, SUM(verdict='bad') AS b FROM feedback "
            "WHERE position_id IS NOT NULL GROUP BY position_id"
        )
        return {r["position_id"]: (int(r["g"] or 0), int(r["b"] or 0)) for r in rows}

    # ---- writes ----
    def save_album(self, rec: dict[str, Any]) -> None:
        cols = ["album_id", "created_at", "seed", "theme_id", "family", "arc_id", "location_id", "her_outfit_id",
                "his_outfit_id", "reference_mode", "character_fp", "character", "positions", "title", "logline", "llm_model"]
        row = {**rec, "created_at": rec.get("created_at") or _now()}
        row["character"] = json.dumps(row.get("character") or {}, ensure_ascii=False)
        row["positions"] = json.dumps(row["positions"])
        self.db.execute(
            f"INSERT OR REPLACE INTO albums ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [row.get(c) for c in cols],
        )
        self.db.commit()

    def add_feedback(self, album_id: str, shots: Iterable[int], verdict: str, reason: str = "") -> int:
        album = self.get(album_id)
        if album is None:
            raise KeyError(album_id)
        positions = json.loads(album["positions"])  # index 0 = shot 2
        n = 0
        for shot in shots:
            pid = positions[shot - 2] if 2 <= shot < len(positions) + 2 else None
            self.db.execute(
                "INSERT INTO feedback (album_id, shot, position_id, verdict, reason, created_at) VALUES (?,?,?,?,?,?)",
                (album_id, shot, pid, verdict, reason, _now()),
            )
            n += 1
        self.db.commit()
        return n

    def set_positions(self, album_id: str, positions: list[str]) -> None:
        """After `albumgen fix` swapped poses: novelty and feedback see what the album really shows."""
        self.db.execute("UPDATE albums SET positions = ? WHERE album_id = ?", (json.dumps(positions), album_id))
        self.db.commit()

    def set_status(self, album_id: str, status: str) -> None:
        self.db.execute("UPDATE albums SET status = ? WHERE album_id = ?", (status, album_id))
        self.db.commit()

    def forget(self, album_id: str) -> None:
        self.db.execute("DELETE FROM feedback WHERE album_id = ?", (album_id,))
        self.db.execute("DELETE FROM albums WHERE album_id = ?", (album_id,))
        self.db.commit()

    # ---- listing ----
    def get(self, album_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM albums WHERE album_id = ?", (album_id,)).fetchone()

    def list(self, n: int = 20) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM albums ORDER BY created_at DESC, rowid DESC LIMIT ?", (n,)).fetchall()

    def total(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM albums").fetchone()[0]
