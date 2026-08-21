#!/usr/bin/env python3
"""Capture exactly one image for nuc_agent.py using the supplied OpenCV approach."""

import argparse
import sys
import time
from pathlib import Path

import cv2


def camera_source(value: str):
    try:
        return int(value)
    except ValueError:
        return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="JPG output path")
    parser.add_argument("--camera", default="0", help="camera index or /dev/videoX")
    parser.add_argument("--warmup-frames", type=int, default=15)
    args = parser.parse_args()

    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    source = camera_source(args.camera)

    capture = cv2.VideoCapture(source, cv2.CAP_V4L2)
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        print(f"cannot open camera: {source}", file=sys.stderr)
        return 2

    try:
        for _ in range(max(args.warmup_frames, 0)):
            capture.read()
            time.sleep(0.03)
        ok, frame = capture.read()
    finally:
        capture.release()

    if not ok or frame is None:
        print("camera returned no frame", file=sys.stderr)
        return 3
    if not cv2.imwrite(str(output), frame):
        print(f"failed to write image: {output}", file=sys.stderr)
        return 4
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
