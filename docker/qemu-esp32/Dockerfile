FROM ubuntu:24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates xz-utils \
    python3 python3-pip python3-venv \
    libsdl2-2.0-0 libslirp0 libglib2.0-0 libpixman-1-0 libgcrypt20 \
    git cmake ninja-build gcc g++ \
    libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install ESP-IDF v5.4
ENV IDF_PATH=/opt/esp-idf
ENV IDF_TOOLS_PATH=/opt/espressif
RUN git clone --depth 1 -b v5.4 https://github.com/espressif/esp-idf.git $IDF_PATH \
    && cd $IDF_PATH && git submodule update --init --depth 1 --recursive \
    && ./install.sh esp32s3 \
    && echo ". $IDF_PATH/export.sh" >> /etc/bash.bashrc

# Install QEMU ESP32 (pre-built binary from Espressif)
RUN cd /tmp && \
    curl -LO https://github.com/espressif/qemu/releases/download/esp-develop-9.2.2-20250817/qemu-xtensa-softmmu-esp_develop_9.2.2_20250817-$(dpkg --print-architecture)-linux-gnu.tar.xz && \
    mkdir -p /opt/qemu && \
    tar xf qemu-xtensa-softmmu-*.tar.xz -C /opt/qemu --strip-components=1 && \
    rm qemu-xtensa-softmmu-*.tar.xz && \
    ln -s /opt/qemu/bin/qemu-system-xtensa /usr/local/bin/qemu-system-xtensa

# Install esptool for flash image creation
RUN pip3 install --break-system-packages esptool

# Working directory
WORKDIR /project

# Entry: source ESP-IDF env, then run command
ENTRYPOINT ["/bin/bash", "-c", ". /opt/esp-idf/export.sh > /dev/null 2>&1 && exec \"$@\"", "--"]
CMD ["bash"]
