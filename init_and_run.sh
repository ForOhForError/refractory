#!/usr/bin/bash
set -e
CHECK_FOR_FILE_DIR=/home/refractory/refractory_data
CHECK_FOR_FILE=$CHECK_FOR_FILE_DIR/update
if ! uv version | diff $CHECK_FOR_FILE -; then
    mkdir -p $CHECK_FOR_FILE_DIR
    uv run python manage.py migrate
    uv version > $CHECK_FOR_FILE
fi
echo "yes" | uv run python manage.py collectstatic
uv run python src/main.py