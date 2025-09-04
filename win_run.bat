set DJANGO_SECRET="SECRETHERE"
uv sync
:loop
uv run python src/main.py
goto loop
pause