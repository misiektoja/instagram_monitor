# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/instagram_monitor

COPY requirements.txt ./
RUN /usr/local/bin/python -m pip install --no-cache-dir -r requirements.txt

COPY instagram_monitor.py ./instagram_monitor.py
COPY instagram_profile_pic_empty.jpg ./instagram_profile_pic_empty.jpg
COPY templates ./templates

RUN chmod 755 /opt/instagram_monitor/instagram_monitor.py

WORKDIR /data

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/python", "/opt/instagram_monitor/instagram_monitor.py"]
CMD ["--help"]
