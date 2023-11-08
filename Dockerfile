FROM python:3.10-slim-bookworm

RUN apt-get update && \
    apt-get install -y nodejs && \
    python3 -m pip install poetry

COPY src/ /app/src/
COPY poetry.lock /app/
COPY pyproject.toml /app/
COPY README.md /app/
WORKDIR /app/
RUN poetry install --no-root
ENTRYPOINT ["poetry", "run", "python", "src/web_server.py"]
