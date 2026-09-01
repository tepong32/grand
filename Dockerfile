# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=src.settings.prod \
    PORT=10000 \
    GRAND_MEDIA_ROOT=/app/runtime/media \
    GRAND_EXPORT_ROOT=/app/runtime/exports \
    GRAND_BACKUP_ROOT=/app/runtime/backups

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends default-mysql-client \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 grand \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/grand --shell /bin/bash grand

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --requirement /app/requirements.txt

COPY --chown=grand:grand . /app
RUN mkdir -p /app/runtime/media /app/runtime/exports /app/runtime/backups /app/staticfiles /app/logs \
    && chown -R grand:grand /app/runtime /app/staticfiles /app/logs

USER grand

# collectstatic needs Django's production storage configuration but no live
# database. These build-only values are never retained as runtime secrets.
RUN SKEY=grand-build-only-not-a-runtime-secret \
    DEFAULT_DB_NAME=build_default \
    DEFAULT_DB_USER=build_default \
    DEFAULT_DB_PASSWORD=build_default \
    FINANCE_DB_NAME=build_finance \
    FINANCE_DB_USER=build_finance \
    FINANCE_DB_PASSWORD=build_finance \
    python manage.py collectstatic --noinput

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '10000') + '/healthz/', timeout=4).read()"

CMD ["sh", "-c", "exec gunicorn src.wsgi:application --bind 0.0.0.0:${PORT:-10000} --access-logfile - --error-logfile -"]
