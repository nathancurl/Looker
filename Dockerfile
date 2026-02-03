FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

VOLUME ["/app/data"]
ENV DB_PATH=/app/data/seen_jobs.db

CMD ["python", "main.py"]
