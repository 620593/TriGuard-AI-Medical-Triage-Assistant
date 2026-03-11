FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TRIGUARD_ENV=production \
    TRIGUARD_LOG_LEVEL=INFO \
    PYTHONPATH=/app

# Install only required OS packages and clean apt cache in same layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for better build caching.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /tmp/requirements.txt

# Copy backend code under /app/backend so imports like backend.src.* resolve reliably.
COPY . /app/backend

# Keep runtime-generated files at stable absolute paths used by hosting mounts.
RUN mkdir -p /app/audio_output /app/nutrition_images && \
    ln -sfn /app/audio_output /app/backend/audio_output && \
    ln -sfn /app/nutrition_images /app/backend/nutrition_images

# Run as non-root in production.
RUN useradd --create-home --shell /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v3/health', timeout=5)"

# Gunicorn with uvicorn workers for production ASGI serving.
CMD ["sh", "-c", "gunicorn backend.src.main:app --worker-class uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:${PORT:-8000} --timeout 120 --graceful-timeout 30 --keep-alive 5 --max-requests 1000 --max-requests-jitter 100"]