#!/usr/bin/env python3
"""Grab one frame from the webcam pointed at the board's screen.

    board_cam.py [out.jpg] [--dev N] [--warm 10]

Bench companion of board_ctl.py: a few warm-up frames let auto-exposure
settle, then one frame is written (default: scratch dir, path printed).
"""
import argparse
import os
import sys
import time

import cv2

ap = argparse.ArgumentParser()
ap.add_argument("out", nargs="?", default=None)
ap.add_argument("--dev", type=int, default=int(os.environ.get("CAM_DEV", "0")))
ap.add_argument("--warm", type=int, default=10)
a = ap.parse_args()

cap = cv2.VideoCapture(a.dev)
if not cap.isOpened():
    sys.exit(f"cannot open /dev/video{a.dev}")
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
for _ in range(a.warm):
    cap.read()
    time.sleep(0.05)
ok, frame = cap.read()
cap.release()
if not ok:
    sys.exit("no frame")
out = a.out or f"/tmp/board_cam_{int(time.time())}.jpg"
cv2.imwrite(out, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
print(out, frame.shape[1], "x", frame.shape[0])
