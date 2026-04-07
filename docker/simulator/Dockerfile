FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Only SDL2 + build tools + VNC — no ESP-IDF needed for native simulator
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config \
    libsdl2-dev \
    x11vnc xvfb fluxbox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /project

# VNC + X11 startup script
RUN printf '#!/bin/bash\nXvfb :99 -screen 0 1024x768x24 &\nexport DISPLAY=:99\nsleep 0.5\nx11vnc -display :99 -forever -nopw -listen 0.0.0.0 -rfbport 5900 &\nfluxbox &\nsleep 0.5\nexec "$@"\n' > /usr/local/bin/start-vnc.sh && chmod +x /usr/local/bin/start-vnc.sh

CMD ["bash"]
