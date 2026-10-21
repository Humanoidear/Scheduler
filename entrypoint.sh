#!/bin/sh
set -e

python3 -c "from app import create_app; create_app()"

exec gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
