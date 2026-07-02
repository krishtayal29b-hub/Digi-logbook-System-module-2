"""
Digilock — Module 2: Digital Shift Logbook
FastAPI backend with SQLite persistence.
Serves the frontend as static files and exposes a JSON API under /api.
"""
import os
import sqlite3
import random
import string
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

DB_PATH = os.path.join(os.path.dirname(__file__), "digilock.db")

app = FastAPI(title="Digilock API — Module 2: Digital Shift Logbook")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'running',
                capacity_pct INTEGER NOT NULL DEFAULT 100
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id TEXT PRIMARY KEY,
                shift TEXT NOT NULL,
                equipment TEXT NOT NULL,
                status TEXT NOT NULL,
                category TEXT NOT NULL,
                operator TEXT NOT NULL,
                notes TEXT NOT NULL,
                has_attachment INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                log_date TEXT NOT NULL
            )
        """)
        # seed equipment once
        cur = db.execute("SELECT COUNT(*) AS c FROM equipment")
        if cur.fetchone()["c"] == 0:
            seed_equipment = [
                ("Compressor Unit B-3", "running", 88),
                ("Boiler Feed Pump", "down", 0),
                ("Conveyor Line 2", "maintenance", 45),
                ("Cooling Tower 1", "running", 92),
                ("HVAC Zone C", "running", 76),
            ]
            db.executemany(
                "INSERT INTO equipment (name, status, capacity_pct) VALUES (?, ?, ?)",
                seed_equipment,
            )
        # seed a handful of logs once
        cur = db.execute("SELECT COUNT(*) AS c FROM logs")
        if cur.fetchone()["c"] == 0:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            seed_logs = [
                ("06:14", "Morning", "Compressor Unit B-3", "running", "Routine", "R. Sharma",
                 "Pressure reading nominal at 6.2 bar. No abnormalities observed during startup checks.", 1),
                ("07:40", "Morning", "Conveyor Line 2", "maintenance", "Maintenance", "A. Verma",
                 "Belt tension adjusted per schedule. Lubrication applied to drive rollers.", 0),
                ("09:05", "Morning", "Cooling Tower 1", "running", "Routine", "R. Sharma",
                 "Water temperature within range. Fan vibration levels normal.", 0),
                ("10:52", "Morning", "Boiler Feed Pump", "down", "Emergency", "S. Iyer",
                 "Unexpected shutdown due to seal leakage. Isolated and tagged out, maintenance notified.", 1),
                ("12:18", "Morning", "Compressor Unit B-3", "running", "Routine", "A. Verma",
                 "Mid-shift check complete. Output steady, no leaks detected.", 0),
                ("13:30", "Morning", "HVAC Zone C", "running", "Routine", "R. Sharma",
                 "Filters inspected, airflow consistent across all vents.", 0),
            ]
            for t, shift, equip, status, cat, op, notes, att in seed_logs:
                db.execute(
                    "INSERT INTO logs (id, shift, equipment, status, category, operator, notes, has_attachment, created_at, log_date) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (gen_log_id(), shift, equip, status, cat, op, notes, att, t, today),
                )


def gen_log_id() -> str:
    return "LOG-" + "".join(random.choices(string.digits, k=4))


init_db()

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LogEntryIn(BaseModel):
    shift: str
    equipment: str = Field(..., min_length=1)
    status: str
    category: str
    operator: str = "Unassigned"
    notes: str = Field(..., min_length=1)
    has_attachment: bool = False


class LogEntryOut(LogEntryIn):
    id: str
    created_at: str
    log_date: str


class EquipmentOut(BaseModel):
    id: int
    name: str
    status: str
    capacity_pct: int


class EquipmentStatusIn(BaseModel):
    status: str
    capacity_pct: Optional[int] = None


VALID_STATUSES = {"running", "maintenance", "down"}
VALID_SHIFTS = {"Morning", "Evening", "Night"}

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"ok": True, "service": "digilock-module2", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/logs", response_model=List[LogEntryOut])
def list_logs(
    shift: str = Query(..., description="Morning | Evening | Night"),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    if shift not in VALID_SHIFTS:
        raise HTTPException(400, "Invalid shift")
    query = "SELECT * FROM logs WHERE shift = ?"
    params: list = [shift]
    if status and status != "all":
        if status not in VALID_STATUSES:
            raise HTTPException(400, "Invalid status filter")
        query += " AND status = ?"
        params.append(status)
    if search:
        query += " AND (equipment LIKE ? OR notes LIKE ? OR operator LIKE ? OR id LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like, like])
    query += " ORDER BY created_at DESC, id DESC"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    return [_row_to_log(r) for r in rows]


@app.post("/api/logs", response_model=LogEntryOut, status_code=201)
def create_log(entry: LogEntryIn):
    if entry.shift not in VALID_SHIFTS:
        raise HTTPException(400, "Invalid shift")
    if entry.status not in VALID_STATUSES:
        raise HTTPException(400, "Invalid status")
    log_id = gen_log_id()
    now = datetime.now(timezone.utc)
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%Y-%m-%d")
    with get_db() as db:
        db.execute(
            "INSERT INTO logs (id, shift, equipment, status, category, operator, notes, has_attachment, created_at, log_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (log_id, entry.shift, entry.equipment, entry.status, entry.category,
             entry.operator, entry.notes, int(entry.has_attachment), time_str, date_str),
        )
        # reflect the change onto the equipment table too, so the right panel stays live
        db.execute(
            "UPDATE equipment SET status = ? WHERE name = ?",
            (entry.status, entry.equipment),
        )
        row = db.execute("SELECT * FROM logs WHERE id = ?", (log_id,)).fetchone()
    return _row_to_log(row)


@app.delete("/api/logs/{log_id}", status_code=204)
def delete_log(log_id: str):
    with get_db() as db:
        cur = db.execute("DELETE FROM logs WHERE id = ?", (log_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Log not found")


@app.get("/api/equipment", response_model=List[EquipmentOut])
def list_equipment():
    with get_db() as db:
        rows = db.execute("SELECT * FROM equipment ORDER BY name").fetchall()
    return [dict(r) for r in rows]


@app.put("/api/equipment/{equipment_id}", response_model=EquipmentOut)
def update_equipment(equipment_id: int, payload: EquipmentStatusIn):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(400, "Invalid status")
    with get_db() as db:
        row = db.execute("SELECT * FROM equipment WHERE id = ?", (equipment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Equipment not found")
        capacity = payload.capacity_pct if payload.capacity_pct is not None else row["capacity_pct"]
        db.execute(
            "UPDATE equipment SET status = ?, capacity_pct = ? WHERE id = ?",
            (payload.status, capacity, equipment_id),
        )
        row = db.execute("SELECT * FROM equipment WHERE id = ?", (equipment_id,)).fetchone()
    return dict(row)


@app.get("/api/stats")
def stats(shift: str = Query(...)):
    if shift not in VALID_SHIFTS:
        raise HTTPException(400, "Invalid shift")
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) AS c FROM logs WHERE shift = ?", (shift,)).fetchone()["c"]
        flagged = db.execute(
            "SELECT COUNT(*) AS c FROM logs WHERE shift = ? AND status IN ('down','maintenance')",
            (shift,),
        ).fetchone()["c"]
    return {"total": total, "flagged": flagged}


def _row_to_log(row) -> dict:
    d = dict(row)
    d["has_attachment"] = bool(d["has_attachment"])
    return d

# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
