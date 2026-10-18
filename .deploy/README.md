# Local / preview deployment

A self-contained stack used to verify that the image deploys and serves traffic.
It runs PostgreSQL plus the application image on port 12000.

## Start

    cd .deploy
    docker compose --env-file .env up -d

`.env` is created on the host and is git-ignored. It must define:

    DJANGO_SECRET_KEY=<50+ random chars>
    DJANGO_ALLOWED_HOSTS=<public hostname>,127.0.0.1,localhost
    CSRF_TRUSTED_ORIGINS=https://<public hostname>
    POSTGRES_DB=cdsp
    POSTGRES_USER=cdsp
    POSTGRES_PASSWORD=<random>

Build the image first if it is missing:

    docker build -t cdsp:latest .

## Verify

    curl -fsS http://127.0.0.1:12000/api/v1/health/   # {"status":"ok","database":"ok"}
    # API docs: http://127.0.0.1:12000/api/v1/docs/

## Logs / stop

    docker compose --env-file .env logs -f web
    docker compose --env-file .env down          # add -v to drop the database volume

## Notes

- This is a preview stack for verification, not the production host. For the real
  deployment see `docs/deployment/coolify.md`.
- `RUN_MIGRATIONS=1` is set, so the entrypoint applies migrations on every start.
- The container health check hits `/api/v1/health/`, which is exempt from the
  HTTPS redirect, so it passes behind a TLS-terminating proxy.
