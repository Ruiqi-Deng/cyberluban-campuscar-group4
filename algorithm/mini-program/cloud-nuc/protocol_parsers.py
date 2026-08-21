"""Pure parsing helpers shared by the NUC agent and offline tests."""

from typing import Any, Dict, Optional, Tuple


def parse_esp32_line(line: str) -> Optional[Dict[str, Any]]:
    if not line.startswith("POS"):
        return None
    parts = line.split(",")
    if len(parts) < 7:
        return None
    try:
        return {
            "lock_status": int(parts[3]),
            "temperature": round(int(parts[4]) / 10.0, 1),
            "humidity": round(int(parts[5]) / 10.0, 1),
            "battery": round(int(parts[6]) / 1000.0, 2),
        }
    except (ValueError, IndexError):
        return None


def parse_nmea_gga(line: str) -> Optional[Tuple[float, float, int]]:
    if not (line.startswith("$GNGGA") or line.startswith("$GPGGA")):
        return None
    parts = line.split(",")
    if len(parts) < 7:
        return None

    def coordinate(raw: str, hemi: str) -> Optional[float]:
        if not raw or hemi not in {"N", "S", "E", "W"}:
            return None
        degree_len = 2 if hemi in {"N", "S"} else 3
        try:
            degrees = int(raw[:degree_len])
            remainder = raw[degree_len:]
            if "." not in remainder:
                remainder = remainder[:2] + "." + remainder[2:]
            minutes = float(remainder)
            if not 0 <= minutes < 60:
                return None
            value = degrees + minutes / 60.0
            return -value if hemi in {"S", "W"} else value
        except (ValueError, IndexError):
            return None

    lat = coordinate(parts[2], parts[3])
    lon = coordinate(parts[4], parts[5])
    try:
        quality = int(parts[6] or 0)
    except ValueError:
        quality = 0
    if lat is None or lon is None:
        return None
    return lat, lon, quality
