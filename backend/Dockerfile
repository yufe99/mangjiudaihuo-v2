FROM python:3.11-slim

WORKDIR /app

# System deps for imageio-ffmpeg + Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Copy source
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]