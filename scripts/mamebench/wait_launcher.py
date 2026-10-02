#!/usr/bin/env python3
"""wait_launcher.py: wait (60 s max) until the board answers ping from the launcher."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from board_ctl import Board
b = Board('/dev/ttyACM0')
t0 = time.time()
while time.time() - t0 < 60:
    p = [x for x in b.send("ping", wait=r"^CTL pong", timeout=3, echo=False) if "pong" in x]
    if p and "launcher" in p[-1]: print(p[-1]); break
    time.sleep(3)
