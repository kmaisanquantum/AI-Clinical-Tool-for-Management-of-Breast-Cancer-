#!/bin/sh
# Startup is best-effort by design: a database that is not ready yet must never
# kill the container, otherwise the platform restarts it in a loop and the web
# server is never reached. Migrations run by default so a fresh deploy works
# with no configuration; set RUN_MIGRATIONS=0 to skip them.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  attempts="${MIGRATE_MAX_ATTEMPTS:-30}"
  i=1
  while [ "$i" -le "$attempts" ]; do
    if python manage.py migrate --noinput; then
      break
    fi
    echo "entrypoint: migrate failed (attempt $i/$attempts), retrying in 2s" >&2
    i=$((i + 1))
    sleep 2
  done
  if [ "$i" -gt "$attempts" ]; then
    echo "entrypoint: migrations did not succeed; starting web server anyway" >&2
  fi

  # Optional demo data so a fresh deployment has a usable login.
  if [ "$SEED_DEMO_DATA" = "1" ]; then
    python manage.py seed_demo_data --doctor-password "${DOCTOR_DEMO_PASSWORD:-doctor}" || echo "entrypoint: seed_demo_data failed; continuing" >&2
  fi
fi
exec "$@"
