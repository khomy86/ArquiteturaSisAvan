FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY streaming_service/ ./streaming_service/

# Create videos directory
RUN mkdir -p /app/videos

# Expose the port the app runs on
EXPOSE 8001

# Command to run the application
CMD ["uvicorn", "streaming_service.main:app", "--host", "0.0.0.0", "--port", "8001"] 