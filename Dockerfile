# One image: the orchestrator API plus the CCC-NeoBank front end at /app/.
# Mirrors the repo layout (/srv/bank_system, /srv/frontend/dist) so the
# project-root-anchored paths (data/orchestrator.db, frontend/dist) resolve
# exactly as they do in a local checkout.

FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000
WORKDIR /srv/bank_system

COPY bank_system/pyproject.toml bank_system/README.md ./
COPY bank_system/src ./src
RUN pip install -e .

# The shipped golden scenario. On Render's free plan the disk is ephemeral,
# so every deploy and cold start begins from this file.
COPY bank_system/data ./data
COPY --from=frontend /build/dist /srv/frontend/dist

EXPOSE 8000
# One worker: P1-P4 state lives in-process over one SQLite file.
# exec: uvicorn becomes PID 1 and receives Render's SIGTERM for a clean shutdown.
CMD ["sh", "-c", "exec uvicorn bank.orchestrator.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
