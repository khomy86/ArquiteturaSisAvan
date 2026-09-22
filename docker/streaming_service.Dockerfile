FROM docker.io/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY streaming_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY streaming_service/ ./streaming_service/

RUN useradd --system --no-create-home app
USER app

EXPOSE 8001
CMD ["uvicorn", "streaming_service.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips", "*"]
