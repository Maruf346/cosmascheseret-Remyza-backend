#!/bin/sh
set -e

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Starting Daphne ASGI server..."
exec daphne cheshara_config.asgi:application \
    --bind 0.0.0.0 \
    --port 8005 \
    --access-log -