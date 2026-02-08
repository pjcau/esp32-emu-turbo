#!/bin/bash
# Wrapper for OpenSCAD in Docker.
# The 'dev' image has EGL support for headless PNG rendering.
# Falls back to xvfb-run if available and EGL fails.
set -euo pipefail
exec openscad "$@"
