# Build from repository root:
#   docker build -f apps/worker/Dockerfile -t axiom-worker .
FROM python:3.12-slim

WORKDIR /app/apps/worker

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY packages/compliance/pyproject.toml packages/compliance/README.md /app/packages/compliance/
COPY packages/compliance/src /app/packages/compliance/src
COPY packages/extractors/pyproject.toml packages/extractors/README.md /app/packages/extractors/
COPY packages/extractors/src /app/packages/extractors/src
COPY apps/worker/pyproject.toml apps/worker/README.md ./
COPY apps/worker/src ./src

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -e /app/packages/compliance \
  && pip install --no-cache-dir -e /app/packages/extractors \
  && pip install --no-cache-dir -e . \
  && python -m playwright install-deps chromium \
  && python -m playwright install chromium

CMD ["celery", "-A", "axiom_worker.celery_app", "worker", "--loglevel=info"]
