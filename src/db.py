# src/db.py
"""Persistenza SQLite. Niente ORM: sono 100 righe di SQL leggibile,
e in sala poter aprire il file e mostrare le query vale più di un layer.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path("/workspace/docrouter.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id      TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    testo       TEXT NOT NULL,
    routing     TEXT NOT NULL,
    reason      TEXT NOT NULL,
    coerenza    INTEGER,          -- 1/0/NULL: NULL = non verificabile
    latency_ms  INTEGER NOT NULL,
    n_tokens    INTEGER
);

CREATE TABLE IF NOT EXISTS fields (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id        TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    value         TEXT NOT NULL,
    confidence    REAL NOT NULL,
    routing       TEXT NOT NULL,
    reason        TEXT NOT NULL,
    mean_logprob  REAL NOT NULL,   -- diagnostica: non decide nulla
    grounding     REAL,            -- NULL = derived
    is_valid      INTEGER NOT NULL
);

-- gli indici servono ai filtri della dashboard
CREATE INDEX IF NOT EXISTS idx_doc_routing ON documents(routing);
CREATE INDEX IF NOT EXISTS idx_doc_created ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fld_doc     ON fields(doc_id);
CREATE INDEX IF NOT EXISTS idx_fld_routing ON fields(routing);
"""


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row          # righe accessibili per nome
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # letture concorrenti mentre si scrive
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as c:
        c.executescript(SCHEMA)


def salva(doc: Any, latency_ms: int, n_tokens: int | None = None) -> None:
    """Persiste un ExtractedDocument."""
    with get_conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO documents
               (doc_id, created_at, testo, routing, reason, coerenza, latency_ms, n_tokens)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                doc.doc_id,
                datetime.now().isoformat(timespec="seconds"),
                doc.testo,
                doc.routing,
                doc.reason,
                None if doc.coerenza_aritmetica is None else int(doc.coerenza_aritmetica),
                latency_ms,
                n_tokens,
            ),
        )
        c.execute("DELETE FROM fields WHERE doc_id = ?", (doc.doc_id,))
        c.executemany(
            """INSERT INTO fields
               (doc_id, name, value, confidence, routing, reason,
                mean_logprob, grounding, is_valid)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [
                (doc.doc_id, f.name, f.value, f.confidence, f.routing,
                 f.reason, f.mean_logprob, f.grounding, int(f.is_valid))
                for f in doc.fields
            ],
        )


def cerca(
    routing: str | None = None,
    campo: str | None = None,
    q: str | None = None,
    solo_scartati: bool = False,
    limit: int = 100,
) -> list[dict]:
    """I filtri della dashboard. WHERE costruito a pezzi, mai f-string:
    i parametri passano sempre come '?' → niente SQL injection."""
    sql = ["SELECT d.* FROM documents d"]
    where: list[str] = []
    params: list[Any] = []

    if campo or solo_scartati:
        sql.append("JOIN fields f ON f.doc_id = d.doc_id")
    if campo:
        where.append("f.name = ?")
        params.append(campo)
    if solo_scartati:
        where.append("f.routing = 'reject'")
    if routing:
        where.append("d.routing = ?")
        params.append(routing)
    if q:
        where.append("(d.testo LIKE ? OR d.doc_id LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    if where:
        sql.append("WHERE " + " AND ".join(where))
    sql.append("GROUP BY d.doc_id ORDER BY d.created_at DESC LIMIT ?")
    params.append(limit)

    with get_conn() as c:
        return [dict(r) for r in c.execute(" ".join(sql), params)]


def leggi(doc_id: str) -> dict | None:
    with get_conn() as c:
        d = c.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        if d is None:
            return None
        fs = c.execute("SELECT * FROM fields WHERE doc_id = ? ORDER BY id", (doc_id,))
        return {**dict(d), "fields": [dict(r) for r in fs]}


def stats() -> dict:
    with get_conn() as c:
        tot = c.execute("SELECT COUNT(*) n FROM documents").fetchone()["n"]
        per_routing = {
            r["routing"]: r["n"]
            for r in c.execute("SELECT routing, COUNT(*) n FROM documents GROUP BY routing")
        }
        lat = c.execute("SELECT AVG(latency_ms) a FROM documents").fetchone()["a"]
        # i campi che falliscono più spesso: dice DOVE il sistema soffre
        top_fail = [
            dict(r)
            for r in c.execute(
                """SELECT name, COUNT(*) n FROM fields
                   WHERE routing = 'reject' GROUP BY name ORDER BY n DESC LIMIT 5"""
            )
        ]
        return {
            "totale": tot,
            "per_routing": per_routing,
            "latenza_media_ms": round(lat or 0),
            "campi_piu_scartati": top_fail,
        }