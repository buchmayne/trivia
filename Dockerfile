# Base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install uv
RUN pip install --no-cache-dir --upgrade uv

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    postgresql-client \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Configure Nginx
COPY nginx.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/

# Create a non-root user and switch to it
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Copy project files
COPY --chown=appuser:appuser . /app/

# Install dependencies
RUN uv sync --frozen --no-dev

# Collect static files
RUN uv run manage.py collectstatic --noinput

# Expose port (optional, useful for debugging locally)
EXPOSE 8000

# Run Django development server by default
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8000", "pub_trivia.wsgi:application"]
