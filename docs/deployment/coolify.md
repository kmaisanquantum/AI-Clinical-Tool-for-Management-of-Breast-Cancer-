# Deployment on Coolify (dspng.space)

Coolify builds this repository from its `Dockerfile`. The image runs migrations
through `entrypoint.sh` and serves the API with Gunicorn.

## 1. Application settings in Coolify

| Setting | Value |
| --- | --- |
| Build pack | Dockerfile |
| Port / exposed port | `8000` |
| Domain | `https://dspng.space` |
| Health check path | `/api/v1/health/` |

## 2. Environment variables

The image boots with **no environment variables at all**: it generates and
persists a secret key, defaults to SQLite, and runs migrations on startup. That
makes it safe against the restart loop, but for a real deployment set these in
the Coolify application (not in a committed `.env`):

    DJANGO_SETTINGS_MODULE=config.settings.prod
    DJANGO_SECRET_KEY=<50+ random chars>
    DJANGO_ALLOWED_HOSTS=dspng.space,www.dspng.space
    CSRF_TRUSTED_ORIGINS=https://dspng.space,https://www.dspng.space
    PORT=8000

Optional:

    RUN_MIGRATIONS=1        # default 1; set 0 to skip migrations on startup
    SEED_DEMO_DATA=1        # load demo users, roles, and rules on boot (patients opt-in via --with-patients)
    DJANGO_SECURE_SSL_REDIRECT=0   # only if the probe sends no X-Forwarded-Proto

Generate a key with:

    python3 -c "import secrets; print(secrets.token_urlsafe(50))"

Add a PostgreSQL database in Coolify and expose its connection URL as
`DATABASE_URL` (Coolify provides this automatically when you link the database).
Without `DATABASE_URL` or `POSTGRES_HOST` the app uses SQLite, which is fine for
a demo but not for multi-replica or production use.

## 3. Health check

`SECURE_SSL_REDIRECT` defaults to `1` in `config.settings.prod`, and
`/api/v1/health/` is in `SECURE_REDIRECT_EXEMPT`, so the liveness probe returns
`200` whether it is called over plain HTTP inside the container or over HTTPS
through the proxy.

If your platform probes the container over plain HTTP *without* sending
`X-Forwarded-Proto`, also set `DJANGO_SECURE_SSL_REDIRECT=0` and rely on the
edge proxy to terminate TLS.

## 4. Verify after deploy

    curl -fsS https://dspng.space/api/v1/health/     # {"status":"ok","database":"ok"}
    curl -fsS https://dspng.space/api/v1/schema/     # OpenAPI schema
    # API docs: https://dspng.space/api/v1/docs/

## 5. Managing Synthetic Demo Patient Data

Patient clinical records are not seeded by default during startup. To optionally seed synthetic demo patient records:

```bash
python manage.py seed_demo --with-patients
```

To purge already-seeded synthetic patient records (`MRN-DEMO-*`) from the running database while preserving system accounts, roles, and guidelines:

```bash
python manage.py purge_demo_data --confirm
```

## Common failures

- **Container restarts in a loop / `Worker failed to boot`** - `DJANGO_SECRET_KEY`
  was unset and older revisions raised on boot. Current code generates and
  persists a key instead of crashing; set `DJANGO_SECRET_KEY` to control it
  explicitly, or `DJANGO_SECRET_KEY_REQUIRED=1` to restore the hard failure.
- **`exec: "/app/entrypoint.sh": permission denied`** - the entrypoint lost its
  executable bit. Keep `entrypoint.sh` mode `100755` in git; the Dockerfile also
  runs `chmod +x` as a safety net.
- **Health check reports unhealthy** - a `301` to HTTPS means the probe is being
  redirected. Confirm `/api/v1/health/` is exempt, or set
  `DJANGO_SECURE_SSL_REDIRECT=0`.
- **`DisallowedHost`** - add the public hostname to `DJANGO_ALLOWED_HOSTS`.
- **CSRF failures on the docs page** - add the full origin (with scheme) to
  `CSRF_TRUSTED_ORIGINS`.
- **Domain shows a different application** - the domain must be assigned to this
  Coolify application's service; check Coolify's Domains tab.
