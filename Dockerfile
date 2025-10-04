FROM python:3.10-slim-bookworm
ARG NODE_MAJOR=22
RUN apt-get update && \
    apt-get install -y ca-certificates curl gnupg && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs libleveldb-dev && \
    python3 -m pip install uv && \
    addgroup --gid 1000 refractory && \
    adduser --uid 1000 --gid 1000 --shell /bin/sh refractory

ENV HOME=/home/refractory
WORKDIR $HOME

COPY --chown=refractory uv.lock .
COPY --chown=refractory pyproject.toml .
COPY --chown=refractory manage.py .
COPY --chown=refractory README.md .

COPY --chown=refractory src/ src/
COPY --chown=refractory static/foundryportal/ static/foundryportal/
COPY --chown=refractory static/refractory/ static/refractory/
COPY --chown=refractory init_and_run.sh .


USER refractory
RUN uv sync
ENTRYPOINT ["bash", "init_and_run.sh"]
