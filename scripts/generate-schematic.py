#!/usr/bin/env python3
"""Thin wrapper: generate multi-sheet KiCad schematics for ESP32 Emu Turbo.

Usage:
    python3 generate-schematic.py [output_dir]

Default output: hardware/kicad/
"""
import sys
import os

# Add scripts dir to path so we can import the package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_schematics.__main__ import main

main()
