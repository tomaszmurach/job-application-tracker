FROM python:3.13-slim

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app main.py config.py database.py models.py schemas.py ./
COPY --chown=app:app routers/ ./routers/
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic/ ./alembic/

USER app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
