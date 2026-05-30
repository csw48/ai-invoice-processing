# ---- builder ----
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./

# Install production deps into /app/.venv
RUN uv sync --frozen --no-dev

# Copy source
COPY app/ ./app/

# ---- final ----
FROM python:3.12-slim

WORKDIR /app

# Non-root user for security
RUN addgroup --system app && adduser --system --ingroup app app

# Copy the virtualenv and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app ./app/

# Activate venv by prepending it to PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
