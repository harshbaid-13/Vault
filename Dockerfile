FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# tzdata: zone files for VAULT_TIMEZONE (TECH_PLAN §8 gotcha 14). Nothing else from apt.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/vault

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY static ./static

# Runs as uid/gid 1000 by default so ./data on the host stays owned by you.
# docker-compose.yml can override with UID/GID.
ARG UID=1000
ARG GID=1000
RUN groupadd --gid "$GID" vault \
 && useradd --uid "$UID" --gid "$GID" --no-create-home --shell /usr/sbin/nologin vault \
 && mkdir -p /data /backups \
 && chown vault:vault /data /backups
USER vault

ENV VAULT_DATA_DIR=/data \
    VAULT_BACKUP_DIR=/backups

EXPOSE 8000
CMD ["python", "-m", "app", "--host", "0.0.0.0", "--port", "8000"]
