FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ml_api/ ./ml_api/
COPY static/ ./static/

RUN mkdir -p /tmp /app/logs

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

EXPOSE 8002

CMD ["uvicorn", "ml_api.main:app", "--host", "0.0.0.0", "--port", "8002"]
