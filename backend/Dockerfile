FROM python:3.14.6-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6

WORKDIR /app

# Avoid writing .pyc under bind-mounted source trees (e.g. docker compose dev).
ENV PYTHONPYCACHEPREFIX=/tmp/pycache
ENV PYTHONPATH=/app

COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /app/requirements.lock

COPY pyproject.toml /app/pyproject.toml
COPY app /app/app
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

# Run the application as a non-root user (least privilege).
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
  && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()" || exit 1

CMD ["hypercorn", "--config", "python:app.hypercorn_config", "app.main:app", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]
