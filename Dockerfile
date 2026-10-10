FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /build
RUN python -m venv "$VIRTUAL_ENV"

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATABASE_PATH=/data/leads.db

RUN groupadd --system app \
    && useradd --system --uid 10001 --gid app --home-dir /app --create-home app \
    && mkdir -p /data \
    && chown -R app:app /data /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app src /app/src
COPY --chown=app:app static /app/static
COPY --chown=app:app templates /app/templates

WORKDIR /app
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"

CMD ["uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"]