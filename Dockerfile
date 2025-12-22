FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# No system packages needed for the current runtime.

WORKDIR /app

# Copy metadata first for better build caching.
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN pip install --no-cache-dir uv && \
    uv export --frozen --no-dev --format requirements-txt > requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt

# Copy source code
COPY src ./src

# Install application package (without dependencies)
RUN pip install --no-cache-dir --no-deps .

# Run as non-root.
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
