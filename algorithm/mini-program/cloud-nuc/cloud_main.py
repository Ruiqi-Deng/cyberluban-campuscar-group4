#!/usr/bin/env python3
"""BioShuttle cloud API.

Run on Tencent Cloud with::

    uvicorn cloud_main:app --host 0.0.0.0 --port 8000

The API stores tasks in SQLite, gives the NUC a small command queue, and keeps
hardware access out of the cloud process.
"""

import base64
import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


DB_PATH = Path(os.getenv("BIOSHUTTLE_DB", "bioshuttle.db"))
EVIDENCE_DIR = Path(os.getenv("BIOSHUTTLE_EVIDENCE_DIR", "evidence"))
ROBOT_TOKEN = os.getenv("BIOSHUTTLE_ROBOT_TOKEN", "")
MAX_EVIDENCE_BYTES = int(os.getenv("BIOSHUTTLE_MAX_EVIDENCE_BYTES", "8000000"))

app = FastAPI(title="BioShuttle API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("BIOSHUTTLE_CORS_ORIGINS", "*").split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db():
    connection = sqlite3.connect(str(DB_PATH), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_code TEXT NOT NULL UNIQUE,
                sample_name TEXT NOT NULL,
                temp_humidity TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                origin_json TEXT NOT NULL,
                target_json TEXT NOT NULL,
                pickup_salt TEXT NOT NULL,
                pickup_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                status_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_code TEXT NOT NULL,
                command_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                state TEXT NOT NULL DEFAULT 'pending',
                robot_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                result_message TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(sample_code) REFERENCES tasks(sample_code)
            );
            CREATE TABLE IF NOT EXISTS robot_state (
                robot_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_code TEXT NOT NULL,
                phase TEXT NOT NULL,
                filename TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                FOREIGN KEY(sample_code) REFERENCES tasks(sample_code)
            );
            """
        )


init_db()


class Location(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    latitude: float
    longitude: float


class TaskCreate(BaseModel):
    sample_name: Optional[str] = None
    sample_type: Optional[str] = None
    temp_humidity: str = Field(min_length=1, max_length=200)
    sender_id: str = Field(default="wechat-user", min_length=1, max_length=100)
    origin: Location
    target: Location


class PickupRequest(BaseModel):
    sample_code: str
    pickup_code: str


class Telemetry(BaseModel):
    robot_id: str = "nuc-01"
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    battery: Optional[float] = None
    lock_status: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rtk_quality: Optional[int] = None
    esp32_connected: Optional[bool] = None
    rtk_connected: Optional[bool] = None
    agent_status: Optional[str] = None
    timestamp: Optional[str] = None


class RobotEvent(BaseModel):
    sample_code: str
    event: str
    message: str = ""


class EvidenceUpload(BaseModel):
    filename: str
    phase: str
    content_base64: str


class CommandAck(BaseModel):
    success: bool
    message: str = ""
    evidence: List[EvidenceUpload] = []


def require_robot_token(x_robot_token: Optional[str] = Header(default=None)) -> None:
    if ROBOT_TOKEN and not secrets.compare_digest(x_robot_token or "", ROBOT_TOKEN):
        raise HTTPException(status_code=401, detail="robot token invalid")


def pickup_digest(code: str, salt: str) -> str:
    return hashlib.sha256((salt + code).encode("utf-8")).hexdigest()


def task_public(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "task_id": row["id"],
        "sample_code": row["sample_code"],
        "sample_name": row["sample_name"],
        "sample_type": row["sample_name"],
        "temp_humidity": row["temp_humidity"],
        "sender_id": row["sender_id"],
        "origin": json.loads(row["origin_json"]),
        "target": json.loads(row["target_json"]),
        "status": row["status"],
        "status_message": row["status_message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_task_row(connection: sqlite3.Connection, sample_code: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM tasks WHERE sample_code = ?", (sample_code,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="样品编码不存在")
    return row


def enqueue(connection: sqlite3.Connection, sample_code: str, command_type: str) -> int:
    now = utc_now()
    cursor = connection.execute(
        "INSERT INTO commands(sample_code, command_type, created_at, updated_at) VALUES(?, ?, ?, ?)",
        (sample_code, command_type, now, now),
    )
    return int(cursor.lastrowid)


def create_task_record(task: TaskCreate) -> Dict[str, Any]:
    sample_name = (task.sample_name or task.sample_type or "").strip()
    if not sample_name:
        raise HTTPException(status_code=422, detail="sample_name 不能为空")
    now = utc_now()
    pickup_code = f"{secrets.randbelow(10000):04d}"
    salt = secrets.token_hex(16)
    with db() as connection:
        cursor = connection.execute(
            """INSERT INTO tasks(
                   sample_code, sample_name, temp_humidity, sender_id,
                   origin_json, target_json, pickup_salt, pickup_hash,
                   status, status_message, created_at, updated_at
               ) VALUES('', ?, ?, ?, ?, ?, ?, ?, 'queued', '等待 NUC 接单', ?, ?)""",
            (
                sample_name,
                task.temp_humidity.strip(),
                task.sender_id.strip(),
                json.dumps(task.origin.model_dump() if hasattr(task.origin, "model_dump") else task.origin.dict(), ensure_ascii=False),
                json.dumps(task.target.model_dump() if hasattr(task.target, "model_dump") else task.target.dict(), ensure_ascii=False),
                salt,
                pickup_digest(pickup_code, salt),
                now,
                now,
            ),
        )
        task_id = int(cursor.lastrowid)
        sample_code = f"BS{datetime.now().strftime('%Y%m%d')}{task_id:04d}"
        connection.execute("UPDATE tasks SET sample_code = ? WHERE id = ?", (sample_code, task_id))
        enqueue(connection, sample_code, "run_delivery")
    return {
        "task_id": task_id,
        "sample_code": sample_code,
        "pickup_code": pickup_code,
        "status": "queued",
        "message": "寄件任务已创建，请妥善保存样品编码和取件码",
    }


@app.get("/")
def health() -> Dict[str, str]:
    return {"message": "BioShuttle Cloud Backend OK", "version": "2.0.0"}


@app.post("/api/tasks")
@app.post("/task/create")
def create_task(task: TaskCreate) -> Dict[str, Any]:
    return create_task_record(task)


@app.get("/api/tasks/{sample_code}")
def task_status(sample_code: str) -> Dict[str, Any]:
    with db() as connection:
        row = get_task_row(connection, sample_code)
        result = task_public(row)
        result["evidence"] = [dict(item) for item in connection.execute(
            "SELECT phase, filename, created_at FROM evidence WHERE sample_code = ? ORDER BY id", (sample_code,)
        ).fetchall()]
        return result


@app.get("/task/status")
def legacy_task_status(task_id: int = Query(...)) -> Dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task_public(row)


@app.get("/tasks")
def list_tasks() -> List[Dict[str, Any]]:
    with db() as connection:
        return [task_public(row) for row in connection.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()]


def request_pickup(sample_code: str, pickup_code: str) -> Dict[str, Any]:
    with db() as connection:
        row = get_task_row(connection, sample_code.strip())
        if row["status"] != "awaiting_pickup":
            raise HTTPException(status_code=409, detail=f"当前状态为 {row['status']}，尚不能取件")
        if not secrets.compare_digest(row["pickup_hash"], pickup_digest(pickup_code.strip(), row["pickup_salt"])):
            raise HTTPException(status_code=400, detail="样品编码或取件码错误")
        now = utc_now()
        connection.execute(
            "UPDATE tasks SET status='pickup_requested', status_message='取件验证通过，等待 NUC 开锁', updated_at=? WHERE sample_code=?",
            (now, sample_code.strip()),
        )
        command_id = enqueue(connection, sample_code.strip(), "release_sample")
    return {"sample_code": sample_code.strip(), "status": "pickup_requested", "command_id": command_id, "message": "验证成功，正在通知小车开锁"}


@app.post("/api/pickup")
def pickup(payload: PickupRequest) -> Dict[str, Any]:
    return request_pickup(payload.sample_code, payload.pickup_code)


@app.post("/task/pickup")
def legacy_pickup(task_id: int, code: str) -> Dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT sample_code FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="任务不存在")
    return request_pickup(row["sample_code"], code)


@app.get("/api/robot/commands/next", dependencies=[Depends(require_robot_token)])
def next_command(robot_id: str = "nuc-01") -> Dict[str, Any]:
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        command = connection.execute("SELECT * FROM commands WHERE state='pending' ORDER BY id LIMIT 1").fetchone()
        if command is None:
            return {"command": None}
        now = utc_now()
        connection.execute(
            "UPDATE commands SET state='running', robot_id=?, updated_at=? WHERE id=? AND state='pending'",
            (robot_id, now, command["id"]),
        )
        task = get_task_row(connection, command["sample_code"])
        if command["command_type"] == "run_delivery":
            connection.execute(
                "UPDATE tasks SET status='to_origin', status_message='NUC 已接单，前往起点', updated_at=? WHERE sample_code=?",
                (now, command["sample_code"]),
            )
        return {
            "command": {
                "id": command["id"],
                "type": command["command_type"],
                "sample_code": command["sample_code"],
                "task": task_public(task),
            }
        }


EVENT_TRANSITIONS = {
    "departed_for_origin": ("to_origin", "NUC 已接单，前往起点"),
    "origin_opened": ("loading", "已到起点并开锁，请寄件人放入样品"),
    "origin_loaded": ("transporting", "样品已装载并闭锁，前往终点"),
    "destination_arrived": ("awaiting_pickup", "已到终点，等待输入样品编码和取件码"),
    "destination_opened": ("unloading", "验证成功，终点已开锁"),
    "completed": ("completed", "样品已取出并闭锁，任务完成"),
    "failed": ("failed", "设备执行失败"),
}


@app.post("/api/robot/events", dependencies=[Depends(require_robot_token)])
def robot_event(payload: RobotEvent) -> Dict[str, Any]:
    if payload.event not in EVENT_TRANSITIONS:
        raise HTTPException(status_code=422, detail="未知机器人事件")
    status, default_message = EVENT_TRANSITIONS[payload.event]
    with db() as connection:
        get_task_row(connection, payload.sample_code)
        connection.execute(
            "UPDATE tasks SET status=?, status_message=?, updated_at=? WHERE sample_code=?",
            (status, payload.message or default_message, utc_now(), payload.sample_code),
        )
    return {"sample_code": payload.sample_code, "status": status}


def store_evidence(connection: sqlite3.Connection, sample_code: str, item: EvidenceUpload) -> str:
    safe_original = Path(item.filename).name
    suffix = Path(safe_original).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".txt"}:
        raise HTTPException(status_code=422, detail="不支持的证据文件格式")
    try:
        content = base64.b64decode(item.content_base64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="证据文件 base64 无效") from exc
    if len(content) > MAX_EVIDENCE_BYTES:
        raise HTTPException(status_code=413, detail="证据文件过大")
    filename = f"{sample_code}_{secrets.token_hex(4)}_{safe_original}"
    (EVIDENCE_DIR / filename).write_bytes(content)
    connection.execute(
        "INSERT INTO evidence(sample_code, phase, filename, created_at) VALUES(?, ?, ?, ?)",
        (sample_code, item.phase, filename, utc_now()),
    )
    return filename


@app.post("/api/robot/commands/{command_id}/ack", dependencies=[Depends(require_robot_token)])
def ack_command(command_id: int, payload: CommandAck) -> Dict[str, Any]:
    saved: List[str] = []
    with db() as connection:
        command = connection.execute("SELECT * FROM commands WHERE id=?", (command_id,)).fetchone()
        if command is None:
            raise HTTPException(status_code=404, detail="命令不存在")
        if command["state"] == "done":
            return {"command_id": command_id, "state": "done", "evidence": []}
        for item in payload.evidence:
            saved.append(store_evidence(connection, command["sample_code"], item))
        state = "done" if payload.success else "failed"
        connection.execute(
            "UPDATE commands SET state=?, result_message=?, updated_at=? WHERE id=?",
            (state, payload.message, utc_now(), command_id),
        )
        if not payload.success:
            connection.execute(
                "UPDATE tasks SET status='failed', status_message=?, updated_at=? WHERE sample_code=?",
                (payload.message or "NUC 命令执行失败", utc_now(), command["sample_code"]),
            )
    return {"command_id": command_id, "state": state, "evidence": saved}


@app.post("/api/robot/telemetry", dependencies=[Depends(require_robot_token)])
@app.post("/robot/upload_status", dependencies=[Depends(require_robot_token)])
def upload_telemetry(payload: Telemetry) -> Dict[str, str]:
    data = payload.model_dump(exclude_none=True) if hasattr(payload, "model_dump") else payload.dict(exclude_none=True)
    data["server_timestamp"] = utc_now()
    with db() as connection:
        connection.execute(
            """INSERT INTO robot_state(robot_id, payload_json, updated_at) VALUES(?, ?, ?)
               ON CONFLICT(robot_id) DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at""",
            (payload.robot_id, json.dumps(data, ensure_ascii=False), data["server_timestamp"]),
        )
    return {"status": "ok"}


@app.get("/api/robot/status")
@app.get("/robot/status")
def robot_status(robot_id: str = "nuc-01") -> Dict[str, Any]:
    with db() as connection:
        state = connection.execute("SELECT * FROM robot_state WHERE robot_id=?", (robot_id,)).fetchone()
        latest = connection.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT 1").fetchone()
        telemetry = json.loads(state["payload_json"]) if state else {}
        return {
            "robot_id": robot_id,
            "telemetry": telemetry,
            "latest_task": task_public(latest) if latest else None,
        }


@app.get("/api/evidence/{filename}")
def get_evidence(filename: str):
    safe_name = Path(filename).name
    path = EVIDENCE_DIR / safe_name
    if safe_name != filename or not path.is_file():
        raise HTTPException(status_code=404, detail="证据文件不存在")
    return FileResponse(path)
