FROM docker.io/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY catalog_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY catalog_service/ ./catalog_service/

RUN useradd --system --no-create-home app
USER app

EXPOSE 8000
CMD ["uvicorn", "catalog_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--timeout-graceful-shutdown", "5"]
