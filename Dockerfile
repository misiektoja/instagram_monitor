# syntax=docker/dockerfile:1
FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/instagram \
    INSTAGRAM_MONITOR_DOCKER=1

WORKDIR /opt/instagram_monitor

COPY requirements.txt ./
RUN /usr/local/bin/python -m pip install --no-cache-dir -r requirements.txt

RUN groupadd --system --gid 10001 instagram && \
    useradd --system --uid 10001 --gid instagram --create-home --home-dir /home/instagram --shell /usr/sbin/nologin instagram

COPY instagram_monitor.py ./instagram_monitor.py
COPY instagram_profile_pic_empty.jpg ./instagram_profile_pic_empty.jpg
COPY templates ./templates

# The session volume is mounted at .config/instaloader and must stay writable when Compose maps the
# container to an arbitrary host UID and GID, so this one directory is world-writable and sticky.
# The sticky bit stops one user removing another user's session, and Instaloader writes each session
# file with mode 0600, so a saved session stays readable only by the account that created it.
RUN chmod 755 /opt/instagram_monitor/instagram_monitor.py && \
    mkdir -p /data /home/instagram/.config/instaloader && \
    chown -R instagram:instagram /opt/instagram_monitor /data /home/instagram && \
    chmod 1777 /home/instagram/.config/instaloader

WORKDIR /data

EXPOSE 8000

USER instagram

ENTRYPOINT ["/usr/local/bin/python", "/opt/instagram_monitor/instagram_monitor.py"]
CMD ["--help"]
