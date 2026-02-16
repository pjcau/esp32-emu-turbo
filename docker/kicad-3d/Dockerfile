FROM kicad/kicad:9.0

USER root
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
    kicad-packages3d python3 && \
    rm -rf /var/lib/apt/lists/*

USER kicad
WORKDIR /project
ENTRYPOINT ["kicad-cli"]
