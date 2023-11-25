FROM python:3.10-slim-bookworm
ARG NODE_MAJOR=20
RUN apt-get update && \
    apt-get install -y ca-certificates curl gnupg
RUN curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
RUN echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list
RUN apt-get update && \
    apt-get install -y nodejs libleveldb-dev && \
    python3 -m pip install poetry

COPY src/ /app/src/
COPY poetry.lock /app/
COPY pyproject.toml /app/
COPY README.md /app/
WORKDIR /app/
RUN poetry install --no-root
ENTRYPOINT ["poetry", "run", "python", "src/main.py"]
