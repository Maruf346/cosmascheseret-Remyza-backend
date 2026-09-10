#!/bin/sh
set -e

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Starting Gunicorn..."
exec gunicorn cheshara_config.wsgi:application \
    --bind 0.0.0.0:8005 \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -