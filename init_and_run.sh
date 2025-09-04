#!/usr/bin/bash
set -e
CHECK_FOR_FILE_DIR=/refractory_data
CHECK_FOR_FILE=$CHECK_FOR_FILE_DIR/update
if [ ! -f $CHECK_FOR_FILE ]; then
    mkdir -p $CHECK_FOR_FILE_DIR
    uv run python manage.py migrate
    echo "yes" | uv run python manage.py collectstatic
    touch $CHECK_FOR_FILE
fi
uv run python src/main.py