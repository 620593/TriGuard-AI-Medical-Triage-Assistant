FROM python:3.10-slim

# Install necessary system dependencies (e.g. for gTTS / audio rendering if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cache layer optimizations)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create static directories for runtime output
RUN mkdir -p audio_output nutrition_images

# Copy the rest of the application
COPY . .

# Default Environment Variables
ENV TRIGUARD_ENV=production
ENV TRIGUARD_LOG_LEVEL=INFO
ENV PYTHONPATH=/app

EXPOSE 8000

# Start Gunicorn via uvicorn workers
CMD ["gunicorn", "src.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
