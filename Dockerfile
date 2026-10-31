FROM node:24-bookworm-slim AS node
FROM python:3.12-slim-bookworm

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && apt-get update \
    && apt-get install -y --no-install-recommends chromium ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PUPPETEER_SKIP_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    SMERGERS_WSGI=1 \
    PORT=5000
WORKDIR /app
COPY requirements.txt requirements-droplet.txt package.json package-lock.json ./
RUN pip install --no-cache-dir -r requirements-droplet.txt \
    && npm ci --no-audit --no-fund
COPY . .
RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p whatsapp/.wwebjs_auth \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 5000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash", "scripts/start-application.sh"]
