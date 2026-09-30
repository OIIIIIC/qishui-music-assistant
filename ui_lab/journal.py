import sqlite3
from datetime import datetime
from pathlib import Path


class Journal:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY, started TEXT NOT NULL, target INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS rounds (
                session_id INTEGER NOT NULL, number INTEGER NOT NULL,
                PRIMARY KEY(session_id, number));
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL,
                stamp TEXT NOT NULL, message TEXT NOT NULL);
        """)

    def session(self, target: int) -> int:
        with self.db:
            return self.db.execute("INSERT INTO sessions(started,target) VALUES (?,?)",
                                   (datetime.now().isoformat(timespec="seconds"), target)).lastrowid

    def record_round(self, session: int, number: int) -> bool:
        with self.db:
            return self.db.execute("INSERT OR IGNORE INTO rounds VALUES (?,?)", (session, number)).rowcount == 1

    def log(self, session: int, message: str):
        with self.db:
            self.db.execute("INSERT INTO events(session_id,stamp,message) VALUES (?,?,?)",
                            (session, datetime.now().isoformat(timespec="seconds"), message))

    def close(self):
        self.db.close()
