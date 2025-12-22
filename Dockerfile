# Jewelry Invoice Bot - Dockerfile
# Multi-stage build for optimized production image

# ============================================================================
# STAGE 1: Builder
# ============================================================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# ============================================================================
# STAGE 2: Production
# ============================================================================
FROM python:3.11-slim as production

# Create non-root user for security
RUN groupadd -r botuser && useradd -r -g botuser botuser

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY --chown=botuser:botuser . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data && chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENVIRONMENT=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.api.health import get_health_checker; import asyncio; asyncio.run(get_health_checker().liveness())" || exit 1

# Run the bot
CMD ["python", "-m", "src.bot.main"]

# ============================================================================
# STAGE 3: Development
# ============================================================================
FROM python:3.11-slim as development

WORKDIR /app

# Install all dependencies including dev tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pytest pytest-asyncio pytest-cov ruff mypy

COPY . .

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=development

CMD ["python", "-m", "src.bot.main"]