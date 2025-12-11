# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with increased timeout and retries
RUN pip install --no-cache-dir --timeout=1000 --retries=5 -r requirements.txt

# Install spaCy English language model
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Pre-download Kokoro models (optional - can be skipped if not using TTS)
RUN python -c "from app.utils.kokoro import download_kokoro_models; download_kokoro_models()" || echo "Kokoro model download skipped (optional)"

# Create necessary directories
RUN mkdir -p /app/audio_output /app/logs /app/data

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

# Copy and set up entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Use entrypoint to fix permissions, then switch to app user
# Keep as root so entrypoint can fix permissions, then su switches to app user
ENTRYPOINT ["docker-entrypoint.sh"]

# Expose port for FastAPI
EXPOSE 8000

# Health check using curl
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command to run FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
