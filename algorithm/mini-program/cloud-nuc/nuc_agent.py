#!/usr/bin/env python3
"""NUC agent: telemetry upload, command polling, lock control, and photos."""

import base64
import json
import logging
import os
import shlex
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import serial

from protocol_parsers import parse_esp32_line, parse_nmea_gga


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bioshuttle-nuc")

CLOUD_BASE_URL = os.getenv("BIOSHUTTLE_CLOUD_URL", "http://111.230.241.59:8000").rstrip("/")
ROBOT_TOKEN = os.getenv("BIOSHUTTLE_ROBOT_TOKEN", "")
ROBOT_ID = os.getenv("BIOSHUTTLE_ROBOT_ID", "nuc-01")
ESP32_PORT = os.getenv("BIOSHUTTLE_ESP32_PORT", "/dev/ttyUSB0")
ESP32_BAUD = int(os.getenv("BIOSHUTTLE_ESP32_BAUD", "115200"))
RTK_PORT = os.getenv("BIOSHUTTLE_RTK_PORT", "/dev/ttyACM3")
RTK_BAUD = int(os.getenv("BIOSHUTTLE_RTK_BAUD", "115200"))
POLL_INTERVAL = float(os.getenv("BIOSHUTTLE_POLL_INTERVAL", "2"))
TELEMETRY_INTERVAL = float(os.getenv("BIOSHUTTLE_TELEMETRY_INTERVAL", "2"))
TRAVEL_SECONDS = float(os.getenv("BIOSHUTTLE_DEMO_TRAVEL_SECONDS", "3"))
HANDOFF_SECONDS = float(os.getenv("BIOSHUTTLE_HANDOFF_SECONDS", "5"))
LOCK_FEEDBACK_TIMEOUT = float(os.getenv("BIOSHUTTLE_LOCK_FEEDBACK_TIMEOUT", "60"))
DRY_RUN = os.getenv("BIOSHUTTLE_DRY_RUN", "1") != "0"
OPEN_COMMAND = os.getenv("BIOSHUTTLE_LOCK_OPEN_COMMAND", "CTRL,0,0,1,0,0")
CLOSE_COMMAND = os.getenv("BIOSHUTTLE_LOCK_CLOSE_COMMAND", "")
CAMERA_COMMAND = os.getenv("BIOSHUTTLE_CAMERA_COMMAND", "")
EVIDENCE_DIR = Path(os.getenv("BIOSHUTTLE_LOCAL_EVIDENCE_DIR", "./nuc_evidence"))

HEADERS = {"X-Robot-Token": ROBOT_TOKEN} if ROBOT_TOKEN else {}
session = requests.Session()

sensor_lock = threading.Lock()
sensor_data: Dict[str, Any] = {
    "temperature": None,
    "humidity": None,
    "battery": None,
    "lock_status": None,
    "esp32_connected": False,
}
position_data: Dict[str, Any] = {
    "latitude": None,
    "longitude": None,
    "rtk_quality": None,
    "rtk_connected": False,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Esp32Device:
    def __init__(self) -> None:
        self.serial: Optional[serial.Serial] = None
        self.io_lock = threading.Lock()

    def connect(self) -> bool:
        if self.serial and self.serial.is_open:
            return True
        try:
            self.serial = serial.Serial(ESP32_PORT, ESP32_BAUD, timeout=0.2, write_timeout=1)
            with sensor_lock:
                sensor_data["esp32_connected"] = True
            logger.info("ESP32 connected: %s", ESP32_PORT)
            return True
        except Exception as exc:
            with sensor_lock:
                sensor_data["esp32_connected"] = False
            logger.warning("ESP32 unavailable: %s", exc)
            return False

    def read_line(self) -> str:
        if not self.connect():
            return ""
        try:
            with self.io_lock:
                assert self.serial is not None
                return self.serial.readline().decode("utf-8", errors="ignore").strip()
        except Exception as exc:
            logger.warning("ESP32 read failed: %s", exc)
            self.close()
            return ""

    def send(self, command: str) -> None:
        if DRY_RUN:
            logger.info("DRY RUN ESP32 command: %s", command or "<not configured>")
            return
        if not command:
            raise RuntimeError("待发送的 ESP32 命令未配置")
        if not self.connect():
            raise RuntimeError("ESP32 串口未连接")
        with self.io_lock:
            assert self.serial is not None
            self.serial.write((command.rstrip("\r\n") + "\n").encode("utf-8"))
            self.serial.flush()

    def close(self) -> None:
        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass
        self.serial = None
        with sensor_lock:
            sensor_data["esp32_connected"] = False


esp32 = Esp32Device()


def esp32_reader() -> None:
    while True:
        parsed = parse_esp32_line(esp32.read_line())
        if parsed:
            with sensor_lock:
                sensor_data.update(parsed)
        time.sleep(0.05)


def rtk_reader() -> None:
    while True:
        try:
            with serial.Serial(RTK_PORT, RTK_BAUD, timeout=1) as port:
                with sensor_lock:
                    position_data["rtk_connected"] = True
                logger.info("RTK connected: %s", RTK_PORT)
                while True:
                    line = port.readline().decode("utf-8", errors="ignore").strip()
                    parsed = parse_nmea_gga(line)
                    if parsed:
                        lat, lon, quality = parsed
                        with sensor_lock:
                            position_data.update(latitude=round(lat, 8), longitude=round(lon, 8), rtk_quality=quality)
        except Exception as exc:
            with sensor_lock:
                position_data["rtk_connected"] = False
            logger.warning("RTK unavailable: %s", exc)
            time.sleep(3)


def request(method: str, path: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("timeout", 10)
    headers = dict(HEADERS)
    headers.update(kwargs.pop("headers", {}))
    response = session.request(method, CLOUD_BASE_URL + path, headers=headers, **kwargs)
    response.raise_for_status()
    return response


def telemetry_loop() -> None:
    while True:
        try:
            with sensor_lock:
                payload = {"robot_id": ROBOT_ID, **sensor_data, **position_data, "timestamp": now_iso(), "agent_status": "dry_run" if DRY_RUN else "online"}
            request("POST", "/api/robot/telemetry", json=payload)
        except Exception as exc:
            logger.warning("telemetry upload failed: %s", exc)
        time.sleep(TELEMETRY_INTERVAL)


def post_event(sample_code: str, event: str, message: str = "") -> None:
    request("POST", "/api/robot/events", json={"sample_code": sample_code, "event": event, "message": message})


def capture(sample_code: str, phase: str) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    extension = ".txt" if DRY_RUN else ".jpg"
    output = EVIDENCE_DIR / f"{sample_code}_{phase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{extension}"
    if DRY_RUN:
        output.write_text(f"DRY RUN evidence: {sample_code} {phase} {now_iso()}\n", encoding="utf-8")
    else:
        if not CAMERA_COMMAND:
            raise RuntimeError("真实模式下必须配置 BIOSHUTTLE_CAMERA_COMMAND")
        args = [piece.replace("{output}", str(output)) for piece in shlex.split(CAMERA_COMMAND)]
        subprocess.run(args, check=True, timeout=30)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"相机命令未生成照片: {output}")
    logger.info("evidence captured: %s", output)
    return output


def wait_for_lock_state(expected: int, action: str) -> None:
    """Wait for the real POS lock feedback: 0=unlocked, 1=locked."""
    if DRY_RUN:
        logger.info("DRY RUN lock feedback: %s", action)
        return
    deadline = time.monotonic() + LOCK_FEEDBACK_TIMEOUT
    while time.monotonic() < deadline:
        with sensor_lock:
            current = sensor_data.get("lock_status")
            connected = sensor_data.get("esp32_connected")
        if connected and current == expected:
            logger.info("lock feedback confirmed: %s (state=%s)", action, current)
            return
        time.sleep(0.1)
    raise RuntimeError(f"等待{action}反馈超时，期望 lock_status={expected}")


def handoff(sample_code: str, location: str) -> List[Tuple[str, Path]]:
    evidence: List[Tuple[str, Path]] = []
    open_phase = f"{location}_after_open"
    close_phase = f"{location}_after_close"
    esp32.send(OPEN_COMMAND)
    wait_for_lock_state(0, "开锁")
    if location == "destination":
        post_event(sample_code, "destination_opened")
    else:
        post_event(sample_code, "origin_opened")
    evidence.append((open_phase, capture(sample_code, open_phase)))
    time.sleep(HANDOFF_SECONDS)
    # 当前硬件没有关锁串口命令：人合上箱门后，机械锁舌自动复位。
    # 若以后换成可电控关锁的型号，可通过环境变量补充命令。
    if CLOSE_COMMAND:
        esp32.send(CLOSE_COMMAND)
    wait_for_lock_state(1, "锁闭")
    evidence.append((close_phase, capture(sample_code, close_phase)))
    return evidence


def execute(command: Dict[str, Any]) -> Tuple[str, List[Tuple[str, Path]]]:
    sample_code = command["sample_code"]
    command_type = command["type"]
    if command_type == "run_delivery":
        post_event(sample_code, "departed_for_origin")
        time.sleep(TRAVEL_SECONDS)
        evidence = handoff(sample_code, "origin")
        post_event(sample_code, "origin_loaded")
        time.sleep(TRAVEL_SECONDS)
        post_event(sample_code, "destination_arrived")
        return "已完成起点取样并到达终点", evidence
    if command_type == "release_sample":
        evidence = handoff(sample_code, "destination")
        post_event(sample_code, "completed")
        return "终点取件完成", evidence
    raise RuntimeError(f"未知命令: {command_type}")


def evidence_payload(items: List[Tuple[str, Path]]) -> List[Dict[str, str]]:
    result = []
    for phase, path in items:
        result.append({
            "filename": path.name,
            "phase": phase,
            "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
        })
    return result


def command_loop() -> None:
    while True:
        command: Optional[Dict[str, Any]] = None
        try:
            command = request("GET", "/api/robot/commands/next", params={"robot_id": ROBOT_ID}).json().get("command")
            if not command:
                time.sleep(POLL_INTERVAL)
                continue
            logger.info("executing command %s", json.dumps(command, ensure_ascii=False))
            message, evidence = execute(command)
            request(
                "POST",
                f"/api/robot/commands/{command['id']}/ack",
                json={"success": True, "message": message, "evidence": evidence_payload(evidence)},
                timeout=60,
            )
        except Exception as exc:
            logger.exception("command execution failed")
            if command:
                try:
                    post_event(command["sample_code"], "failed", str(exc))
                    request("POST", f"/api/robot/commands/{command['id']}/ack", json={"success": False, "message": str(exc), "evidence": []})
                except Exception:
                    logger.exception("failed to report command error")
            time.sleep(POLL_INTERVAL)


def validate_configuration() -> None:
    if not DRY_RUN:
        missing = [name for name, value in {
            "BIOSHUTTLE_CAMERA_COMMAND": CAMERA_COMMAND,
        }.items() if not value]
        if missing:
            raise SystemExit("真实模式缺少配置: " + ", ".join(missing))


if __name__ == "__main__":
    validate_configuration()
    logger.info("NUC agent starting: cloud=%s robot=%s dry_run=%s", CLOUD_BASE_URL, ROBOT_ID, DRY_RUN)
    threading.Thread(target=esp32_reader, daemon=True).start()
    threading.Thread(target=rtk_reader, daemon=True).start()
    threading.Thread(target=telemetry_loop, daemon=True).start()
    command_loop()
