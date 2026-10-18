# Deployment with Nixpacks

This project includes a `nixpacks.toml` configuration file for zero-config buildpack deployments on platforms that support Nixpacks (such as Railway, Coolify, Render, Fly.io, or Dokku).

## Build and Start Lifecycle

Nixpacks automatically configures the application environment based on `nixpacks.toml`:

1. **Setup Phase**: Installs Python 3.12 runtime and pip (`python312`, `python312Packages.pip`).
2. **Install Phase**: Initializes virtual environment `/opt/venv` and installs dependencies via `pip install -r requirements.txt`.
3. **Build Phase**: Collects static files via `python manage.py collectstatic --noinput`.
4. **Start Phase**: Runs database migrations and starts the Gunicorn web server:
   ```bash
   python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
   ```

## Local Nixpacks Build

To test building locally with the Nixpacks CLI:

```bash
nixpacks build . -t cdsp-app
docker run -p 8000:8000 -e DJANGO_SECRET_KEY=secret -e DATABASE_URL=postgres://user:pass@host:5432/db cdsp-app
```

## Recommended Environment Variables

Configure the following environment variables in your deployment platform settings:

| Variable | Description | Example |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | Settings module | `config.settings.prod` |
| `DJANGO_SECRET_KEY` | Cryptographic secret key | `generate-a-secure-random-key` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgres://user:pass@db-host:5432/dbname` |
| `DJANGO_ALLOWED_HOSTS` | Allowed hostnames | `yourdomain.com,.onrender.com,.railway.app` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF (full scheme) | `https://yourdomain.com` |
| `PORT` | Application port | `8000` |

> Note: the CSRF variable is `CSRF_TRUSTED_ORIGINS` (not `DJANGO_CSRF_TRUSTED_ORIGINS`)
> and values must include the scheme, e.g. `https://dspng.space`.
