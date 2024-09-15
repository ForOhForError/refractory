set DJANGO_SECRET="SECRETHERE"
poetry install
:loop
poetry run python src/main.py
goto loop
pause