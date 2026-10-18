FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-dev.txt ./
# Test tooling (pytest/ruff) is only installed when explicitly requested.
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then \
        pip install --no-cache-dir -r requirements-dev.txt; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi
COPY . .
# collectstatic needs no database and no real secret (base.py provides a build fallback).
RUN DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py collectstatic --noinput
RUN chmod +x /app/entrypoint.sh \
    && useradd -m appuser && chown -R appuser /app
USER appuser
ENTRYPOINT ["/app/entrypoint.sh"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/api/v1/health/" || exit 1
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3"]
