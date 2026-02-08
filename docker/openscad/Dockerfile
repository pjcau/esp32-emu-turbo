FROM openscad/openscad:dev

# The 'dev' tag uses EGL for headless rendering and does not require xvfb.
# It is based on a newer Debian release with valid package repos.

WORKDIR /project

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
