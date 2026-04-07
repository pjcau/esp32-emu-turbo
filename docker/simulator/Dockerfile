FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# SDL2 + build tools + X11/VNC for display forwarding
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build pkg-config \
    python3 python3-pip python3-venv \
    libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev \
    git curl ca-certificates \
    x11vnc xvfb fluxbox \
    && rm -rf /var/lib/apt/lists/*

# ESP-IDF v5.4 (linux target support)
ENV IDF_PATH=/opt/esp-idf
ENV IDF_TOOLS_PATH=/opt/espressif
RUN git clone --depth 1 -b v5.5.4 https://github.com/espressif/esp-idf.git $IDF_PATH \
    && cd $IDF_PATH && git submodule update --init --depth 1 --recursive \
    && ./install.sh esp32s3 \
    && echo ". $IDF_PATH/export.sh" >> /etc/bash.bashrc

WORKDIR /project

# VNC + X11 startup script
RUN echo '#!/bin/bash\n\
Xvfb :99 -screen 0 800x600x24 &\n\
export DISPLAY=:99\n\
sleep 1\n\
x11vnc -display :99 -forever -nopw -listen 0.0.0.0 -rfbport 5900 &\n\
fluxbox &\n\
exec "$@"' > /usr/local/bin/start-vnc.sh && chmod +x /usr/local/bin/start-vnc.sh

ENTRYPOINT ["/bin/bash", "-c", ". /opt/esp-idf/export.sh > /dev/null 2>&1 && exec \"$@\"", "--"]
CMD ["bash"]
