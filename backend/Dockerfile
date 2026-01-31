FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir -U pip

COPY pyproject.toml /app/pyproject.toml
COPY app /app/app
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
