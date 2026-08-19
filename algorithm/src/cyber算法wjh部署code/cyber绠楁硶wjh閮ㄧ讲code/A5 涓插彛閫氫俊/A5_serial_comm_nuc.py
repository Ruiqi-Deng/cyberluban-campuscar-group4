#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BioShuttle A5 - NUC 与电控板串口联调程序

运行环境：
    Ubuntu 22.04 / NUC
    Python 3.10+
    pyserial

安装：
    python3 -m pip install pyserial

查看串口：
    python3 A5_serial_comm_nuc.py --list-ports

连接：
    python3 A5_serial_comm_nuc.py --port /dev/ttyUSB0
    python3 A5_serial_comm_nuc.py --port /dev/ttyACM0

协议：
    NUC -> 电控：
        CTRL,<左速>,<右速>,<锁指令>,<开盖指令>,<拍照指令>\n

    电控 -> NUC：
        POS,<左编码器>,<右编码器>,<锁状态>,<温度x10>,<湿度x10>,<电压mV>\n

锁定义：
    lock_cmd:
        0 = 关锁
        1 = 开锁

    lock_status:
        0 = 解锁
        1 = 锁闭

注意：
1. 本程序运行在 NUC 上，不是运行在单片机上。
2. 开锁命令只发送一次，避免电磁锁线圈被重复触发。
3. “发送成功”只表示数据写入串口；只有收到 POS 锁状态反馈，
   才表示链路闭环成功。
"""

from __future__ import annotations

import argparse
import math
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional

import serial
from serial.tools import list_ports


# ============================================================
# 数据结构
# ============================================================

@dataclass(frozen=True)
class CtrlCommand:
    """NUC 下发给电控板的 CTRL 指令。"""

    left_speed: float = 0.0
    right_speed: float = 0.0
    lock_cmd: int = 0
    lid_cmd: int = 0
    photo_cmd: int = 0

    def validate(self) -> None:
        for name, value in (
            ("left_speed", self.left_speed),
            ("right_speed", self.right_speed),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} 不是有效数字")
            if not -1.0 <= value <= 1.0:
                raise ValueError(f"{name} 必须位于 -1.0 ~ 1.0")

        if self.lock_cmd not in (0, 1):
            raise ValueError("lock_cmd 只能为 0 或 1")

        if self.lid_cmd not in (0, 1, 2):
            raise ValueError("lid_cmd 只能为 0、1 或 2")

        if self.photo_cmd not in (0, 1):
            raise ValueError("photo_cmd 只能为 0 或 1")


@dataclass(frozen=True)
class PosData:
    """电控板上报给 NUC 的 POS 数据。"""

    left_encoder: int
    right_encoder: int
    lock_status: int
    temperature: float
    humidity: float
    battery_voltage: float
    received_time: float


# ============================================================
# 协议构建与解析
# ============================================================

def build_ctrl_frame(
    command: CtrlCommand,
    speed_mode: str = "normalized",
) -> str:
    """
    构建 CTRL 帧。

    speed_mode:
        normalized:
            发送 -1.00 ~ 1.00
            例如 CTRL,0.50,-0.20,0,0,0

        pwm1000:
            将 -1.0 ~ 1.0 映射为 -1000 ~ 1000
            例如 CTRL,500,-200,0,0,0

    只测电子锁时左右速度为 0，两种模式都不会影响锁测试。
    """
    command.validate()

    if speed_mode == "normalized":
        left_text = f"{command.left_speed:.2f}"
        right_text = f"{command.right_speed:.2f}"

    elif speed_mode == "pwm1000":
        left_text = str(round(command.left_speed * 1000))
        right_text = str(round(command.right_speed * 1000))

    else:
        raise ValueError(
            "speed_mode 必须是 normalized 或 pwm1000"
        )

    return (
        f"CTRL,"
        f"{left_text},"
        f"{right_text},"
        f"{command.lock_cmd},"
        f"{command.lid_cmd},"
        f"{command.photo_cmd}\n"
    )


def parse_pos_frame(line: str) -> Optional[PosData]:
    """
    解析一条 POS 帧。

    正确示例：
        POS,123,125,1,255,550,11800

    对应：
        左编码器 123
        右编码器 125
        锁闭
        温度 25.5℃
        湿度 55.0%
        电压 11.8V
    """
    text = line.strip()

    if not text.startswith("POS,"):
        return None

    parts = text.split(",")

    if len(parts) != 7:
        return None

    try:
        left_encoder = int(parts[1])
        right_encoder = int(parts[2])
        lock_status = int(parts[3])
        temperature_raw = int(parts[4])
        humidity_raw = int(parts[5])
        battery_mv = int(parts[6])

    except ValueError:
        return None

    # 防止乱码恰好能被 int() 解析后混入有效数据
    if lock_status not in (0, 1):
        return None

    if not -1000 <= temperature_raw <= 2000:
        return None

    if not 0 <= humidity_raw <= 1000:
        return None

    if not 0 <= battery_mv <= 100000:
        return None

    return PosData(
        left_encoder=left_encoder,
        right_encoder=right_encoder,
        lock_status=lock_status,
        temperature=temperature_raw / 10.0,
        humidity=humidity_raw / 10.0,
        battery_voltage=battery_mv / 1000.0,
        received_time=time.monotonic(),
    )


# ============================================================
# NUC 串口通信类
# ============================================================

class SerialComm:
    """NUC 与电控板之间的串口通信。"""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        speed_mode: str = "normalized",
        read_timeout: float = 0.2,
        print_raw_rx: bool = False,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.speed_mode = speed_mode
        self.read_timeout = read_timeout
        self.print_raw_rx = print_raw_rx

        self.serial_port: Optional[serial.Serial] = None

        self._running = threading.Event()
        self._rx_thread: Optional[threading.Thread] = None
        self._write_lock = threading.Lock()
        self._data_lock = threading.Lock()

        self.latest_pos: Optional[PosData] = None

        self.valid_pos_count = 0
        self.invalid_pos_count = 0
        self.other_line_count = 0

    def connect(self) -> None:
        """打开串口并启动后台接收线程。"""
        if self.serial_port is not None and self.serial_port.is_open:
            return

        self.serial_port = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.read_timeout,
            write_timeout=1.0,
        )

        # 某些 Arduino/USB 串口板在打开串口时会自动复位
        time.sleep(1.2)

        self.serial_port.reset_input_buffer()
        self.serial_port.reset_output_buffer()

        self._running.set()

        self._rx_thread = threading.Thread(
            target=self._receive_loop,
            name="a5_serial_rx",
            daemon=True,
        )
        self._rx_thread.start()

    def disconnect(self) -> None:
        """停止接收线程并关闭串口。"""
        self._running.clear()

        if self._rx_thread is not None:
            self._rx_thread.join(timeout=1.0)

        if self.serial_port is not None:
            try:
                if self.serial_port.is_open:
                    self.serial_port.close()
            finally:
                self.serial_port = None

    def send_command(self, command: CtrlCommand) -> str:
        """
        发送一条 CTRL 指令。

        返回不含换行符的文本，便于终端打印。
        """
        if self.serial_port is None or not self.serial_port.is_open:
            raise RuntimeError("串口尚未连接")

        frame = build_ctrl_frame(
            command=command,
            speed_mode=self.speed_mode,
        )

        payload = frame.encode("ascii")

        with self._write_lock:
            written_size = self.serial_port.write(payload)
            self.serial_port.flush()

        if written_size != len(payload):
            raise serial.SerialTimeoutException(
                f"串口发送不完整："
                f"{written_size}/{len(payload)} bytes"
            )

        return frame.rstrip("\n")

    def send_lock(self, unlock: bool) -> str:
        """
        发送开锁或关锁指令。

        unlock=True:
            CTRL,0,0,1,0,0

        unlock=False:
            CTRL,0,0,0,0,0
        """
        command = CtrlCommand(
            left_speed=0.0,
            right_speed=0.0,
            lock_cmd=1 if unlock else 0,
            lid_cmd=0,
            photo_cmd=0,
        )

        return self.send_command(command)

    def send_motion(
        self,
        left_speed: float,
        right_speed: float,
        lock_cmd: int = 0,
    ) -> str:
        """发送左右轮速度，预留给后续 A4 状态机调用。"""
        command = CtrlCommand(
            left_speed=left_speed,
            right_speed=right_speed,
            lock_cmd=lock_cmd,
            lid_cmd=0,
            photo_cmd=0,
        )

        return self.send_command(command)

    def send_stop(self, lock_cmd: int = 0) -> str:
        """发送停车指令。"""
        return self.send_motion(
            left_speed=0.0,
            right_speed=0.0,
            lock_cmd=lock_cmd,
        )

    def get_latest_pos(self) -> Optional[PosData]:
        """线程安全地取得最新 POS。"""
        with self._data_lock:
            return self.latest_pos

    def get_pos_age(self) -> Optional[float]:
        """返回最新 POS 距当前的秒数。"""
        pos = self.get_latest_pos()

        if pos is None:
            return None

        return time.monotonic() - pos.received_time

    def is_healthy(self, max_pos_age: float = 0.6) -> bool:
        """
        判断通信是否健康。

        POS 设计频率为 10Hz；
        若超过 0.6 秒没有有效 POS，则视为通信异常。
        """
        age = self.get_pos_age()

        return (
            self.serial_port is not None
            and self.serial_port.is_open
            and age is not None
            and age <= max_pos_age
        )

    def wait_for_lock_status(
        self,
        expected_status: int,
        timeout: float = 2.0,
        after_time: Optional[float] = None,
    ) -> bool:
        """
        等待新的锁状态反馈。

        expected_status:
            0 = 解锁
            1 = 锁闭
        """
        if expected_status not in (0, 1):
            raise ValueError("expected_status 只能是 0 或 1")

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            pos = self.get_latest_pos()

            if (
                pos is not None
                and pos.lock_status == expected_status
                and (
                    after_time is None
                    or pos.received_time >= after_time
                )
            ):
                return True

            time.sleep(0.02)

        return False

    def _receive_loop(self) -> None:
        """后台接收循环。"""
        if self.serial_port is None:
            return

        while self._running.is_set():
            try:
                raw = self.serial_port.readline()

                if not raw:
                    continue

                # readline 超时可能返回没有 \n 的半帧
                if not raw.endswith(b"\n"):
                    self.invalid_pos_count += 1
                    print(
                        f"\n⚠️ 收到不完整数据：{raw!r}",
                        flush=True,
                    )
                    continue

                line = raw.decode(
                    "ascii",
                    errors="replace",
                ).strip()

                if self.print_raw_rx:
                    print(f"\n⬅️ RX: {line}", flush=True)

                pos = parse_pos_frame(line)

                if pos is not None:
                    with self._data_lock:
                        self.latest_pos = pos

                    self.valid_pos_count += 1

                elif line.startswith("POS,"):
                    self.invalid_pos_count += 1
                    print(
                        f"\n⚠️ POS 帧格式错误：{line}",
                        flush=True,
                    )

                else:
                    # 单片机可能输出启动日志，不算 POS 解析失败
                    self.other_line_count += 1
                    print(
                        f"\n[电控板日志] {line}",
                        flush=True,
                    )

            except (
                serial.SerialException,
                OSError,
            ) as error:
                if self._running.is_set():
                    print(
                        f"\n❌ 串口接收异常：{error}",
                        flush=True,
                    )

                self._running.clear()
                break


# ============================================================
# 终端联调功能
# ============================================================

def print_available_ports() -> None:
    """列出 NUC 当前识别到的串口设备。"""
    ports = list(list_ports.comports())

    if not ports:
        print("没有发现串口设备。")
        print("请检查 USB 线、驱动以及电控板供电。")
        return

    print("NUC 当前发现以下串口：")

    for item in ports:
        print(
            f"  设备：{item.device}\n"
            f"  描述：{item.description}\n"
            f"  VID:PID："
            f"{item.vid!s}:{item.pid!s}\n"
        )


def print_latest_status(comm: SerialComm) -> None:
    """打印最新一帧 POS。"""
    pos = comm.get_latest_pos()

    if pos is None:
        print(
            "尚未收到有效 POS。\n"
            f"有效 POS 数：{comm.valid_pos_count}\n"
            f"错误 POS 数：{comm.invalid_pos_count}\n"
            f"其他日志数：{comm.other_line_count}"
        )
        return

    age = time.monotonic() - pos.received_time
    lock_text = "锁闭" if pos.lock_status == 1 else "解锁"

    print(
        f"左编码器：{pos.left_encoder}\n"
        f"右编码器：{pos.right_encoder}\n"
        f"锁状态：{lock_text} ({pos.lock_status})\n"
        f"温度：{pos.temperature:.1f} ℃\n"
        f"湿度：{pos.humidity:.1f} %\n"
        f"电压：{pos.battery_voltage:.3f} V\n"
        f"最近 POS 帧龄：{age:.3f} s\n"
        f"通信健康：{'是' if comm.is_healthy() else '否'}"
    )


def run_joint_test_cli(comm: SerialComm) -> None:
    """NUC 端交互式联调菜单。"""
    print(
        "\n================ A5 联调命令 ================\n"
        "open\n"
        "    发送开锁指令，等待 lock_status=0\n\n"
        "close\n"
        "    发送关锁指令，等待 lock_status=1\n\n"
        "status\n"
        "    查看最新 POS 和通信状态\n\n"
        "move <左速> <右速>\n"
        "    发送运动指令，例如：move 0.2 0.2\n\n"
        "stop\n"
        "    左右轮速度置零\n\n"
        "raw <完整帧>\n"
        "    直接发送原始帧，调试时使用\n\n"
        "quit\n"
        "    退出程序\n"
        "=============================================\n"
    )

    while True:
        try:
            user_input = input("A5-NUC> ").strip()

        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not user_input:
            continue

        parts = user_input.split()
        command = parts[0].lower()

        try:
            if command in ("quit", "exit", "q"):
                break

            if command in ("status", "s"):
                print_latest_status(comm)
                continue

            if command in ("open", "unlock", "o"):
                send_time = time.monotonic()
                frame = comm.send_lock(unlock=True)

                print(f"➡️ TX: {frame}")

                confirmed = comm.wait_for_lock_status(
                    expected_status=0,
                    timeout=2.0,
                    after_time=send_time,
                )

                if confirmed:
                    print("✅ 已收到新 POS：电子锁为解锁状态")

                else:
                    print(
                        "⚠️ 指令已经写入串口，"
                        "但 2 秒内未收到新的 lock_status=0。\n"
                        "请检查：\n"
                        "1. 电控板是否收到 CTRL 帧；\n"
                        "2. 电磁锁驱动是否动作；\n"
                        "3. 限位开关/霍尔传感器是否接好；\n"
                        "4. 电控板是否持续发送 POS。"
                    )

                continue

            if command in ("close", "lock", "c"):
                send_time = time.monotonic()
                frame = comm.send_lock(unlock=False)

                print(f"➡️ TX: {frame}")

                confirmed = comm.wait_for_lock_status(
                    expected_status=1,
                    timeout=2.0,
                    after_time=send_time,
                )

                if confirmed:
                    print("✅ 已收到新 POS：电子锁为锁闭状态")

                else:
                    print(
                        "⚠️ 指令已经写入串口，"
                        "但 2 秒内未收到新的 lock_status=1。\n"
                        "请检查锁状态传感器和 POS 上报。"
                    )

                continue

            if command == "move":
                if len(parts) != 3:
                    print(
                        "格式错误，应为："
                        "move <左速> <右速>"
                    )
                    continue

                left_speed = float(parts[1])
                right_speed = float(parts[2])

                frame = comm.send_motion(
                    left_speed=left_speed,
                    right_speed=right_speed,
                    lock_cmd=0,
                )

                print(f"➡️ TX: {frame}")
                continue

            if command == "stop":
                frame = comm.send_stop(lock_cmd=0)
                print(f"➡️ TX: {frame}")
                continue

            if command == "raw":
                if len(parts) < 2:
                    print("格式错误，应为：raw CTRL,...")
                    continue

                if (
                    comm.serial_port is None
                    or not comm.serial_port.is_open
                ):
                    raise RuntimeError("串口尚未连接")

                raw_text = user_input[4:].rstrip("\r\n") + "\n"
                raw_bytes = raw_text.encode("ascii")

                with comm._write_lock:
                    comm.serial_port.write(raw_bytes)
                    comm.serial_port.flush()

                print(f"➡️ TX RAW: {raw_text.rstrip()}")
                continue

            print(
                "未知命令。可用命令："
                "open / close / status / move / stop / raw / quit"
            )

        except ValueError as error:
            print(f"❌ 参数错误：{error}")

        except (
            RuntimeError,
            serial.SerialException,
            OSError,
        ) as error:
            print(f"❌ 操作失败：{error}")


# ============================================================
# 程序入口
# ============================================================

def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="BioShuttle A5 NUC 串口联调程序"
    )

    parser.add_argument(
        "--port",
        help="串口设备，例如 /dev/ttyUSB0 或 /dev/ttyACM0",
    )

    parser.add_argument(
        "--baudrate",
        type=int,
        default=115200,
        help="串口波特率，默认 115200",
    )

    parser.add_argument(
        "--speed-mode",
        choices=("normalized", "pwm1000"),
        default="normalized",
        help=(
            "速度字段格式："
            "normalized=-1.00~1.00，"
            "pwm1000=-1000~1000"
        ),
    )

    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="列出串口后退出",
    )

    parser.add_argument(
        "--raw-rx",
        action="store_true",
        help="打印每一条收到的原始串口文本",
    )

    return parser


def main() -> int:
    parser = create_argument_parser()
    args = parser.parse_args()

    if args.list_ports:
        print_available_ports()
        return 0

    if not args.port:
        print_available_ports()
        print(
            "\n请通过 --port 指定串口，例如：\n"
            "python3 A5_serial_comm_nuc.py "
            "--port /dev/ttyUSB0"
        )
        return 2

    comm = SerialComm(
        port=args.port,
        baudrate=args.baudrate,
        speed_mode=args.speed_mode,
        print_raw_rx=args.raw_rx,
    )

    try:
        comm.connect()

        print(
            f"✅ NUC 串口已连接\n"
            f"设备：{args.port}\n"
            f"波特率：{args.baudrate}\n"
            f"格式：8N1\n"
            f"速度模式：{args.speed_mode}"
        )

        run_joint_test_cli(comm)
        return 0

    except (
        serial.SerialException,
        OSError,
    ) as error:
        print(f"❌ 无法打开串口：{error}")

        print(
            "\n常见处理：\n"
            "1. 检查设备名是否正确；\n"
            "2. 执行：ls -l /dev/ttyUSB* /dev/ttyACM*\n"
            "3. 将当前用户加入 dialout：\n"
            "   sudo usermod -aG dialout $USER\n"
            "4. 注销并重新登录 NUC。"
        )

        return 1

    finally:
        comm.disconnect()
        print("🔌 串口已关闭")


if __name__ == "__main__":
    sys.exit(main())
