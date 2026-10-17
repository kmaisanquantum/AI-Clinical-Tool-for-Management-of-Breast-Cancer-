#!/bin/sh
# Migrations are best-effort: a database that is not ready yet must not kill the
# container, otherwise the platform restarts it in a loop and never reaches the
# web server. Wait briefly for the database, then continue regardless.
if [ "$RUN_MIGRATIONS" = "1" ]; then
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
fi
exec "$@"
