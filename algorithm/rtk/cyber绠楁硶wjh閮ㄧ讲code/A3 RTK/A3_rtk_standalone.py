#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
A3 RTK 独立读取测试程序（非 ROS2 版）

功能：
1. 从串口读取 NMEA GGA 数据
2. 识别定位质量：单点 / 差分 / RTK 固定解 / RTK 浮点解
3. 连续获得若干帧 RTK 固定解后，将当前位置设为局部原点
4. 将经纬度转换为局部 East/North 米制坐标
5. 检测数据超时，避免重复使用过期位置
6. 显示接收频率、卫星数和 HDOP

安装依赖：
    pip3 install pyserial pynmea2

运行示例：
    python3 a3_rtk_standalone.py --port /dev/ttyUSB0 --baud 115200

查看串口：
    ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import pynmea2
import serial
from serial.tools import list_ports


EARTH_RADIUS_M = 6_371_000.0

QUALITY_LABELS = {
    0: "无效",
    1: "单点定位",
    2: "差分定位",
    4: "RTK固定解",
    5: "RTK浮点解",
}


@dataclass
class RTKFix:
    latitude: float
    longitude: float
    altitude: float
    quality: int
    satellites: int
    hdop: Optional[float]
    received_at: float

    @property
    def has_position(self) -> bool:
        return self.quality in (1, 2, 4, 5)

    @property
    def is_rtk(self) -> bool:
        return self.quality in (4, 5)

    @property
    def is_fixed(self) -> bool:
        return self.quality == 4


class LocalENUConverter:
    """
    将经纬度近似转换为局部 ENU 平面坐标。

    适合校园内、短距离测试。x 为东向，y 为北向，单位为米。
    """

    def __init__(self) -> None:
        self.ref_lat: Optional[float] = None
        self.ref_lon: Optional[float] = None

    @property
    def ready(self) -> bool:
        return self.ref_lat is not None and self.ref_lon is not None

    def set_origin(self, latitude: float, longitude: float) -> None:
        self.ref_lat = latitude
        self.ref_lon = longitude

    def to_enu(self, latitude: float, longitude: float) -> tuple[float, float]:
        if not self.ready:
            raise RuntimeError("局部坐标原点尚未设置")

        assert self.ref_lat is not None
        assert self.ref_lon is not None

        lat_diff = math.radians(latitude - self.ref_lat)
        lon_diff = math.radians(longitude - self.ref_lon)
        cos_ref_lat = math.cos(math.radians(self.ref_lat))

        east = lon_diff * EARTH_RADIUS_M * cos_ref_lat
        north = lat_diff * EARTH_RADIUS_M
        return east, north


class RTKSerialReader:
    def __init__(self, port: str, baudrate: int, timeout: float = 0.2) -> None:
        self.port = port
        self.baudrate = baudrate
        self.serial_port = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
        )

    def close(self) -> None:
        if self.serial_port.is_open:
            self.serial_port.close()

    def read_gga(self) -> Optional[RTKFix]:
        """
        读取一行串口数据。

        非 GGA 语句返回 None；
        合法 GGA 返回 RTKFix；
        解析失败时打印简短警告并返回 None。
        """
        raw = self.serial_port.readline()
        if not raw:
            return None

        line = raw.decode("ascii", errors="ignore").strip()
        if not line.startswith("$"):
            return None

        try:
            message = pynmea2.parse(line, check=True)
        except pynmea2.ChecksumError:
            print("⚠️ NMEA 校验和错误，已丢弃该帧", file=sys.stderr)
            return None
        except pynmea2.ParseError:
            return None

        if getattr(message, "sentence_type", "") != "GGA":
            return None

        try:
            quality = int(message.gps_qual or 0)
            satellites = int(message.num_sats or 0)
            altitude = float(message.altitude or 0.0)
            hdop = float(message.horizontal_dil) if message.horizontal_dil else None
            latitude = float(message.latitude)
            longitude = float(message.longitude)
        except (TypeError, ValueError):
            return None

        return RTKFix(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            quality=quality,
            satellites=satellites,
            hdop=hdop,
            received_at=time.monotonic(),
        )


def print_available_ports() -> None:
    ports = list(list_ports.comports())
    if not ports:
        print("没有检测到串口设备。")
        return

    print("检测到以下串口：")
    for item in ports:
        description = item.description or "未知设备"
        print(f"  {item.device:<20} {description}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A3 RTK 独立读取测试程序")
    parser.add_argument(
        "--port",
        help="RTK 串口，例如 /dev/ttyUSB0 或 /dev/ttyACM0",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="串口波特率，默认 115200",
    )
    parser.add_argument(
        "--origin-fixed-count",
        type=int,
        default=5,
        help="连续收到多少帧 RTK 固定解后设置原点，默认 5",
    )
    parser.add_argument(
        "--stale-timeout",
        type=float,
        default=0.5,
        help="超过多少秒没有新 GGA 数据视为超时，默认 0.5 秒",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="列出可用串口后退出",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_ports:
        print_available_ports()
        return 0

    if not args.port:
        print("❌ 请通过 --port 指定 RTK 串口。\n")
        print_available_ports()
        print("\n示例：python3 a3_rtk_standalone.py --port /dev/ttyUSB0")
        return 2

    try:
        reader = RTKSerialReader(args.port, args.baud)
    except serial.SerialException as exc:
        print(f"❌ 无法打开串口 {args.port}: {exc}")
        print("请检查设备名、USB 连接和 dialout 权限。")
        return 1

    converter = LocalENUConverter()
    fixed_count = 0
    recent_gga_times: deque[float] = deque()
    last_gga_time: Optional[float] = None
    timeout_reported = False

    print("=" * 88)
    print("A3 RTK 独立读取测试")
    print(f"串口：{args.port}    波特率：{args.baud}")
    print("等待 GGA 数据。建议将天线置于室外开阔处并保持朝上。")
    print("按 Ctrl+C 退出。")
    print("=" * 88)

    try:
        while True:
            fix = reader.read_gga()
            now = time.monotonic()

            if fix is None:
                if (
                    last_gga_time is not None
                    and now - last_gga_time > args.stale_timeout
                    and not timeout_reported
                ):
                    print(
                        f"⚠️ 超过 {args.stale_timeout:.1f}s 未收到新 GGA 数据，"
                        "当前定位数据不可继续使用。"
                    )
                    timeout_reported = True
                continue

            last_gga_time = fix.received_at
            timeout_reported = False

            recent_gga_times.append(fix.received_at)
            while recent_gga_times and fix.received_at - recent_gga_times[0] > 2.0:
                recent_gga_times.popleft()

            receive_hz = (
                (len(recent_gga_times) - 1)
                / (recent_gga_times[-1] - recent_gga_times[0])
                if len(recent_gga_times) >= 2
                and recent_gga_times[-1] > recent_gga_times[0]
                else 0.0
            )

            if fix.is_fixed:
                fixed_count += 1
            else:
                fixed_count = 0

            if not converter.ready and fixed_count >= args.origin_fixed_count:
                converter.set_origin(fix.latitude, fix.longitude)
                print(
                    "\n✅ 已连续获得 RTK 固定解，设置局部原点："
                    f"({fix.latitude:.8f}, {fix.longitude:.8f})\n"
                )

            quality_label = QUALITY_LABELS.get(fix.quality, f"未知({fix.quality})")
            hdop_text = f"{fix.hdop:.2f}" if fix.hdop is not None else "--"

            if converter.ready and fix.has_position:
                east, north = converter.to_enu(fix.latitude, fix.longitude)
                position_text = f"E {east:+8.3f} m  N {north:+8.3f} m"
            else:
                position_text = "E/N 尚未建立（等待连续 RTK 固定解）"

            print(
                f"{position_text} | "
                f"纬度 {fix.latitude:.8f} 经度 {fix.longitude:.8f} | "
                f"{quality_label:<8} | 卫星 {fix.satellites:02d} | "
                f"HDOP {hdop_text:>5} | GGA {receive_hz:4.1f} Hz"
            )

    except KeyboardInterrupt:
        print("\n已停止 RTK 读取。")
    finally:
        reader.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
