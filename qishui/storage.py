from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("QISHUI_DATA_DIR")
    path = Path(override) if override else Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "QishuiAssistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


DEFAULTS = {"target": 20, "max_minutes": 30, "round_timeout": 180,
            "platform": "auto", "hdc": "", "adb": "", "serial": ""}


def load_settings() -> dict:
    try:
        settings = json.loads((data_dir() / "settings.json").read_text("utf-8"))
        result = DEFAULTS | {k: v for k, v in settings.items() if k in DEFAULTS}
        for key, lo, hi in (("target", 1, 100), ("max_minutes", 1, 240), ("round_timeout", 60, 600)):
            result[key] = max(lo, min(hi, int(result[key])))
        if result["platform"] not in ("auto", "harmony", "android"):
            result["platform"] = "auto"
        for key in ("hdc", "adb", "serial"):
            if not isinstance(result[key], str):
                result[key] = ""
        return result
    except (OSError, ValueError, TypeError, AttributeError):
        return dict(DEFAULTS)


def save_settings(value: dict):
    path = data_dir() / "settings.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(path)


class Journal:
    """A round is persisted before entering an ad; success is an idempotent update."""
    def __init__(self, path: Path | None = None):
        self.db = sqlite3.connect(path or data_dir() / "history.sqlite3")
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY, started TEXT NOT NULL, target INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'running');
            CREATE TABLE IF NOT EXISTS rounds (
                id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL, started TEXT NOT NULL,
                status TEXT NOT NULL, evidence TEXT NOT NULL DEFAULT '', observed INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, session_id INTEGER, time TEXT NOT NULL, message TEXT NOT NULL);
        """)
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(rounds)")}
        if "observed" not in columns:
            with self.db:
                self.db.execute("ALTER TABLE rounds ADD COLUMN observed INTEGER NOT NULL DEFAULT 0")
                self.db.execute("UPDATE rounds SET observed=1 WHERE status IN ('watching','success')")

    @staticmethod
    def now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def recover(self):
        with self.db:
            self.db.execute("UPDATE rounds SET status='uncertain', evidence='程序中断，结果未确认' WHERE status IN ('pending','watching')")
            self.db.execute("UPDATE sessions SET status='interrupted' WHERE status='running'")

    def session(self, target: int) -> int:
        with self.db:
            return self.db.execute("INSERT INTO sessions(started,target) VALUES (?,?)", (self.now(), target)).lastrowid

    def begin(self, session: int) -> int:
        with self.db:
            return self.db.execute("INSERT INTO rounds(session_id,started,status) VALUES (?,?,'pending')", (session, self.now())).lastrowid

    def watching(self, round_id: int):
        with self.db:
            self.db.execute("UPDATE rounds SET status='watching', observed=1 WHERE id=? AND status='pending'", (round_id,))

    def success(self, round_id: int, evidence: str) -> bool:
        with self.db:
            cur = self.db.execute("UPDATE rounds SET status='success', evidence=? WHERE id=? AND status IN ('pending','watching')", (evidence, round_id))
            return cur.rowcount == 1

    def uncertain(self, round_id: int, reason: str):
        with self.db:
            self.db.execute("UPDATE rounds SET status='uncertain', evidence=? WHERE id=? AND status IN ('pending','watching')", (reason, round_id))

    def finish(self, session: int, status: str):
        with self.db:
            self.db.execute("UPDATE sessions SET status=? WHERE id=?", (status, session))

    def event(self, session: int | None, message: str):
        with self.db:
            self.db.execute("INSERT INTO events(session_id,time,message) VALUES (?,?,?)", (session, self.now(), message))

    def counts(self, session: int) -> dict:
        rows = dict(self.db.execute("SELECT status,COUNT(*) FROM rounds WHERE session_id=? GROUP BY status", (session,)))
        started = self.db.execute("SELECT COALESCE(SUM(observed),0) FROM rounds WHERE session_id=?", (session,)).fetchone()[0]
        return {"success": rows.get("success", 0), "started": started,
                "uncertain": rows.get("uncertain", 0)}

    def history(self) -> list[tuple]:
        return self.db.execute("SELECT time,message FROM events ORDER BY id DESC LIMIT 200").fetchall()

    def latest(self) -> tuple | None:
        return self.db.execute("SELECT id,target,status FROM sessions ORDER BY id DESC LIMIT 1").fetchone()

    def close(self):
        self.db.close()
