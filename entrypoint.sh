#!/bin/sh
set -e

python3 -c "from app import init_db; init_db()"

exec gunicorn -k gthread -w 4 --threads 8 --timeout 60 --keep-alive 5 -b 0.0.0.0:5000 "app:app"
