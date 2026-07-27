set DJANGO_SECRET="SECRETHERE"
set DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost/
set DJANGO_ALLOWED_HOSTS=localhost
uv sync
:loop
uv run python src/main.py
goto loop
pause