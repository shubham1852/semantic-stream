# ==============================================================================
# SemanticStream — Backend Dockerfile  (fast build, no gcc in builder)
# All packages in requirements-docker.txt ship as pre-built wheels —
# no C compiler or FFmpeg is needed at pip-install time.
# ==============================================================================

# ── Stage 1: pip install only ────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /workspace

# No apt packages needed — all wheels are pre-built binaries
COPY requirements-docker.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements-docker.txt


# ── Stage 2: minimal runtime ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /workspace

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Install ONLY runtime system libraries (not build tools)
# ffmpeg-python and av call the ffmpeg binary at runtime; opencv needs these libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY . ./backend/

# Create storage directories
RUN mkdir -p backend/storage/uploads backend/storage/processed \
             backend/storage/frames backend/storage/reports

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /workspace
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
