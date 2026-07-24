# Copy node binaries from official node image
FROM node:22-slim as legacy-node
FROM node:24-slim as current-node
# Runtime container
FROM python:3.10-slim-bookworm

COPY --from=legacy-node /usr/local/bin/node /usr/local/bin/node-old
COPY --from=current-node /usr/local/bin/node /usr/local/bin/node

RUN apt-get update && \
    apt-get update && \
    apt-get install -y libleveldb-dev tini && \
    python3 -m pip install uv && \
    addgroup --gid 10001 --system refractory && \
    adduser --uid 10000 --system --ingroup refractory --home /home/refractory refractory 

ENTRYPOINT ["tini", "--", "bash"]

ENV HOME=/home/refractory
WORKDIR $HOME

COPY --chown=refractory uv.lock .
COPY --chown=refractory pyproject.toml .
COPY --chown=refractory manage.py .
COPY --chown=refractory README.md .

USER refractory
RUN uv sync && mkdir -p refractory_data foundry_releases_zip foundry_releases instance_data db
COPY --chown=refractory src/ src/
COPY --chown=refractory static/foundryportal/ static/foundryportal/
COPY --chown=refractory static/refractory/ static/refractory/
COPY --chown=refractory init_and_run.sh .

CMD ["init_and_run.sh"]
