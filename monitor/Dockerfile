FROM python:3.14-slim

# Security: Run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir -e .

# Copy monitor service and dependencies
COPY monitor_service.py gmail_client.py ./

# Create directories with proper permissions
RUN mkdir -p /app/config /app/state && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV GMAIL_CREDENTIALS_FILE=/app/config/credentials.json
ENV GMAIL_TOKEN_FILE=/app/config/token.json
ENV STATE_FILE=/app/state/livetrack_state.json
ENV PYTHONUNBUFFERED=1

# Run monitor service
CMD ["python", "-u", "monitor_service.py"]
