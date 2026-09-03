# Base image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# `uv run` syncs the environment before executing and includes the dev group
# by default, which would undo the `--no-dev` build below and re-install
# numpy/pandas on every container start. The venv baked into the image is
# already the environment we want, so never sync at runtime.
ENV UV_NO_SYNC=1
ENV UV_FROZEN=1

# Install uv
RUN pip install --no-cache-dir --upgrade uv

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and switch to it
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Copy project files
COPY --chown=appuser:appuser . /app/

# Install dependencies
RUN uv sync --frozen --no-dev

# Expose port (optional, useful for debugging locally)
EXPOSE 8000

# Run Django development server by default
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8000", "pub_trivia.wsgi:application"]
