# Build from repository root:
#   docker build -f apps/api/Dockerfile -t axiom-api .
FROM python:3.12-slim

WORKDIR /app/apps/api

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY packages/compliance/pyproject.toml packages/compliance/README.md /app/packages/compliance/
COPY packages/compliance/src /app/packages/compliance/src
COPY packages/extractors/pyproject.toml packages/extractors/README.md /app/packages/extractors/
COPY packages/extractors/src /app/packages/extractors/src
COPY packages/exporters/pyproject.toml packages/exporters/README.md /app/packages/exporters/
COPY packages/exporters/src /app/packages/exporters/src
COPY apps/api/pyproject.toml apps/api/README.md ./
COPY apps/api/src ./src

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -e /app/packages/compliance \
  && pip install --no-cache-dir -e /app/packages/extractors \
  && pip install --no-cache-dir -e /app/packages/exporters \
  && pip install --no-cache-dir -e . \
  && python -m playwright install-deps chromium \
  && python -m playwright install chromium

EXPOSE 8000

CMD ["uvicorn", "axiom_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
