# ==============================================================================
# SemanticStream — Backend Dockerfile
# Multi-stage build: slim Python 3.11 image with FFmpeg
# ==============================================================================

# Stage 1: dependency builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools and FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# Stage 2: lean runtime image
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy FFmpeg binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY . .

# Create storage directories (volume-mounted in compose)
RUN mkdir -p storage/uploads storage/processed storage/frames storage/reports

# Non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
