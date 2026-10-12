#!/bin/sh
set -eu
cd /app
case "${1:-}" in
  bootstrap)
    # Initial deployment only, one replica. Later releases migrate separately.
    /app/entrypoint.sh release
    exec /app/entrypoint.sh web
    ;;
  web)
    python manage.py wait_for_db
    python manage.py migrate --check
    python manage.py collectstatic --noinput
    exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --timeout 60 --error-logfile - --access-logfile - --access-logformat '%(s)s %(L)s'
    ;;
  release)
    python manage.py wait_for_db
    python manage.py migrate --noinput
    ;;
  *) exec "$@" ;;
esac
